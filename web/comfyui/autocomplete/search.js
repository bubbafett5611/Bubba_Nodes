// Search indexing and scoring logic

import { normalizeSearchText, normalizeAliases } from './utils.js';

export function scoreTextMatch(rawText, queryVariations) {
	const text = String(rawText || "").toLowerCase();
	if (!text || !queryVariations.length) {
		return 0;
	}

	const normalizedText = normalizeSearchText(text);
	const compactText = normalizedText.replace(/\s+/g, "");
	const preparedQueries = buildPreparedQueries(queryVariations);
	return scorePreparedText(normalizedText, compactText, preparedQueries);
}

export function scorePreparedText(normText, compactText, preparedQueries) {
	let best = 0;
	for (const query of preparedQueries) {
		const normalizedQuery = query.norm;
		const compactQuery = query.compact;
		if (!normalizedQuery) {
			continue;
		}

		if (normText === normalizedQuery) {
			best = Math.max(best, 1200);
		}
		if (normText.startsWith(normalizedQuery)) {
			best = Math.max(best, 1050);
		}
		if (normText.includes(` ${normalizedQuery}`)) {
			best = Math.max(best, 900);
		}

		const idxNorm = normText.indexOf(normalizedQuery);
		if (idxNorm >= 0) {
			best = Math.max(best, 780 - Math.min(idxNorm, 200));
		}

		if (compactQuery && compactText === compactQuery) {
			best = Math.max(best, 1000);
		}
		if (compactQuery && compactText.startsWith(compactQuery)) {
			best = Math.max(best, 860);
		}
		if (compactQuery) {
			const idxCompact = compactText.indexOf(compactQuery);
			if (idxCompact >= 0) {
				best = Math.max(best, 700 - Math.min(idxCompact, 200));
			}
		}
	}

	return best;
}

export function buildPreparedQueries(queryVariations) {
	const prepared = [];
	const seen = new Set();
	for (const query of queryVariations) {
		const norm = normalizeSearchText(query);
		if (!norm || seen.has(norm)) {
			continue;
		}
		seen.add(norm);
		prepared.push({
			norm,
			compact: norm.replace(/\s+/g, ""),
		});
	}
	return prepared;
}

function addIndexBucket(map, key, index) {
	if (!key) {
		return;
	}
	const list = map.get(key);
	if (list) {
		list.push(index);
		return;
	}
	map.set(key, [index]);
}

function addPrefixBuckets(map, key, index) {
	if (!key) {
		return;
	}
	addIndexBucket(map, key.slice(0, 1), index);
	addIndexBucket(map, key.slice(0, 2), index);
	addIndexBucket(map, key.slice(0, 3), index);
}

function collectTokenKeys(values) {
	const keys = new Set();
	for (const value of values) {
		if (!value) {
			continue;
		}
		keys.add(value);
		keys.add(value.replace(/\s+/g, ""));
		for (const part of value.split(/\s+/g)) {
			if (part) {
				keys.add(part);
			}
		}
	}
	return [...keys.values()].filter(Boolean);
}

export function buildSearchIndex(words) {
	const entries = [];
	const prefixBuckets = new Map();

	for (let i = 0; i < words.length; i += 1) {
		const item = words[i];
		const textNorm = normalizeSearchText(item.text);
		const textCompact = textNorm.replace(/\s+/g, "");
		const aliasNorm = normalizeAliases(item.aliases).map((alias) => normalizeSearchText(alias)).filter(Boolean);
		const aliasCompact = aliasNorm.map((alias) => alias.replace(/\s+/g, ""));

		entries.push({
			item,
			textNorm,
			textCompact,
			aliasNorm,
			aliasCompact,
		});

		const keys = collectTokenKeys([textNorm, textCompact, ...aliasNorm, ...aliasCompact]);
		for (const key of keys) {
			addPrefixBuckets(prefixBuckets, key, i);
		}
	}

	return {
		entries,
		prefixBuckets,
	};
}

let searchIndexCache = {
	wordsRef: null,
	index: null,
};

export function getSearchIndex(words) {
	if (searchIndexCache.wordsRef === words && searchIndexCache.index) {
		return searchIndexCache.index;
	}
	const index = buildSearchIndex(words);
	searchIndexCache.wordsRef = words;
	searchIndexCache.index = index;
	return index;
}

export function findMatchesFromIndex(index, queryVariations) {
	const preparedQueries = buildPreparedQueries(queryVariations);
	if (!preparedQueries.length) {
		return [];
	}

	const candidateIndices = new Set();
	for (const query of preparedQueries) {
		const keys = [
			query.norm.slice(0, 3),
			query.norm.slice(0, 2),
			query.norm.slice(0, 1),
			query.compact.slice(0, 3),
			query.compact.slice(0, 2),
			query.compact.slice(0, 1),
		].filter(Boolean);

		for (const key of keys) {
			const bucket = index.prefixBuckets.get(key);
			if (!bucket) {
				continue;
			}
			for (let i = 0; i < bucket.length; i += 1) {
				candidateIndices.add(bucket[i]);
			}
		}
	}

	if (!candidateIndices.size) {
		for (let i = 0; i < index.entries.length; i += 1) {
			candidateIndices.add(i);
		}
	}

	const matched = [];
	for (const idx of candidateIndices) {
		const entry = index.entries[idx];
		let bestScore = scorePreparedText(entry.textNorm, entry.textCompact, preparedQueries);
		let bestAlias = null;

		for (let i = 0; i < entry.aliasNorm.length; i += 1) {
			const aliasScore = scorePreparedText(entry.aliasNorm[i], entry.aliasCompact[i], preparedQueries) - 20;
			if (aliasScore > bestScore) {
				bestScore = aliasScore;
				bestAlias = entry.aliasNorm[i];
			}
		}

		if (bestScore > 0) {
			matched.push({
				...entry.item,
				matchScore: bestScore,
				matchedAlias: bestAlias,
			});
		}
	}

	return matched;
}

export function invalidateSearchIndexCache() {
	searchIndexCache.wordsRef = null;
	searchIndexCache.index = null;
}

export function findMatchMetadata(item, queryVariations) {
	if (!item?.text || !queryVariations.length) {
		return null;
	}

	const text = String(item.text || "");
	const aliases = Array.isArray(item.aliases) ? item.aliases : [];
	let bestScore = scoreTextMatch(text, queryVariations);
	let bestAlias = null;

	for (const alias of aliases) {
		const aliasScore = scoreTextMatch(alias, queryVariations) - 20;
		if (aliasScore > bestScore) {
			bestScore = aliasScore;
			bestAlias = alias;
		}
	}

	if (bestScore <= 0) {
		return null;
	}

	return {
		score: bestScore,
		matchedAlias: bestAlias,
	};
}
