const { ComfyWidgets } = window.comfyAPI.widgets;

const customWordsStorageKey = "bubba.Autocomplete.CustomWords";
const danbooruTagsStorageKey = "bubba.Autocomplete.DanbooruTags";
const danbooruMetaStorageKey = "bubba.Autocomplete.DanbooruMeta";
const bundledCacheSchemaVersion = 1;

const LOCAL_DANBOORU_MERGED_CSV_URL = new URL("./danbooru_e621_merged.csv", import.meta.url);

let danbooruTagsMemoryCache = [];
let danbooruTagsVersion = 0;
let mergedWordListCache = {
	key: null,
	words: [],
};
let searchIndexCache = {
	wordsRef: null,
	index: null,
};

{
	const style = document.createElement("style");
	style.textContent = `
		.bubba-autocomplete {
			position: fixed;
			z-index: 99999;
			background: var(--comfy-menu-bg);
			color: var(--input-text);
			border: 1px solid var(--border-color);
			border-radius: 6px;
			box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
			max-height: 220px;
			overflow-y: auto;
			min-width: 220px;
			font-size: 12px;
		}
		.bubba-autocomplete-item {
			padding: 6px 10px;
			cursor: pointer;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.bubba-autocomplete-item.selected {
			background: rgba(100, 140, 255, 0.25);
		}
		.bubba-autocomplete-item-meta {
			opacity: 0.75;
			margin-left: 8px;
		}
		.bubba-autocomplete-item-alt {
			opacity: 0.85;
			margin-left: 8px;
			font-style: italic;
		}
	`;
	document.body.appendChild(style);
}

function toInt(value, fallback) {
	const parsed = Number.parseInt(String(value), 10);
	if (Number.isNaN(parsed)) {
		return fallback;
	}
	return parsed;
}

function formatNumber(value) {
	return new Intl.NumberFormat().format(value);
}

function normalizeDanbooruCategory(value) {
	const category = toInt(value, -1);
	if (category < 0) {
		return null;
	}
	return category;
}

function getDanbooruCategoryLabel(value) {
	switch (normalizeDanbooruCategory(value)) {
		case 0:
			return "general";
		case 1:
			return "artist";
		case 2:
			return "unknown";
		case 3:
			return "copyright";
		case 4:
			return "character";
		case 5:
			return "meta";
		default:
			return null;
	}
}

function parseJsonStorage(key, fallback) {
	try {
		const raw = localStorage.getItem(key);
		if (!raw) {
			return fallback;
		}
		return JSON.parse(raw);
	} catch (error) {
		return fallback;
	}
}

function normalizeSearchText(value) {
	return String(value || "")
		.toLowerCase()
		.replace(/[\/_:\-]+/g, " ")
		.replace(/[^a-z0-9\s]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

function normalizeAliases(value) {
	if (!value) {
		return [];
	}
	const raw = Array.isArray(value) ? value : String(value).split(/[|,]/g);
	const deduped = new Set();
	for (const item of raw) {
		let alias = String(item || "").trim();
		if (alias.startsWith('"') && alias.endsWith('"') && alias.length >= 2) {
			alias = alias.slice(1, -1);
		}
		if (alias.startsWith("'") && alias.endsWith("'") && alias.length >= 2) {
			alias = alias.slice(1, -1);
		}
		if (!alias) {
			continue;
		}
		deduped.add(alias.toLowerCase());
	}
	return [...deduped.values()];
}

function parseCsvRow(line) {
	const text = String(line || "");
	if (!text) {
		return [];
	}

	const parts = [];
	let current = "";
	let inQuotes = false;

	for (let i = 0; i < text.length; i += 1) {
		const ch = text[i];
		if (ch === '"') {
			if (inQuotes && text[i + 1] === '"') {
				current += '"';
				i += 1;
				continue;
			}
			inQuotes = !inQuotes;
			continue;
		}
		if (ch === "," && !inQuotes) {
			parts.push(current.trim());
			current = "";
			continue;
		}
		current += ch;
	}

	parts.push(current.trim());
	return parts;
}

function toCsvField(value) {
	const text = String(value ?? "");
	if (!text.includes(",") && !text.includes('"') && !text.includes("\n") && !text.includes("\r")) {
		return text;
	}
	return `"${text.replace(/"/g, '""')}"`;
}

function mergeAliases(left, right) {
	const merged = new Set([...(left || []), ...(right || [])]);
	return [...merged.values()];
}

function parseCustomWordEntry(rawText) {
	const text = String(rawText || "").trim();
	if (!text) {
		return null;
	}

	if (text.includes("=>")) {
		const [canonicalRaw, aliasesRaw] = text.split("=>", 2);
		const canonical = String(canonicalRaw || "").trim();
		if (!canonical) {
			return null;
		}
		return {
			text: canonical,
			aliases: normalizeAliases(aliasesRaw),
		};
	}

	if (text.includes("|")) {
		const parts = text
			.split("|")
			.map((part) => part.trim())
			.filter(Boolean);
		if (!parts.length) {
			return null;
		}
		return {
			text: parts[0],
			aliases: normalizeAliases(parts.slice(1)),
		};
	}

	return {
		text,
		aliases: [],
	};
}

function getSearchQueryVariations(query) {
	const trimmed = String(query || "").trim().toLowerCase();
	if (!trimmed) {
		return [];
	}

	const variants = new Set([trimmed, normalizeSearchText(trimmed)]);

	if (trimmed.includes(" ")) {
		variants.add(trimmed.replace(/\s+/g, "_"));
		variants.add(trimmed.replace(/\s+/g, ""));
	}

	if (trimmed.includes("_")) {
		variants.add(trimmed.replace(/_+/g, " "));
		variants.add(trimmed.replace(/_+/g, ""));
	}

	const spaceParts = trimmed.split(/\s+/g).filter(Boolean);
	if (spaceParts.length > 1) {
		variants.add(spaceParts[spaceParts.length - 1]);
	}

	for (const value of [...variants]) {
		const normalized = normalizeSearchText(value);
		variants.add(normalized);
		variants.add(normalized.replace(/\s+/g, "_"));
		variants.add(normalized.replace(/\s+/g, ""));
	}

	return [...variants.values()].filter(Boolean).slice(0, 12);
}

function normalizeEntry(entry, source) {
	if (!entry) {
		return null;
	}

	if (typeof entry === "string") {
		const parsed = parseCustomWordEntry(entry);
		const text = String(parsed?.text || "").trim();
		if (!text) {
			return null;
		}
		return {
			text,
			source,
			count: null,
			aliases: normalizeAliases(parsed?.aliases),
		};
	}

	if (typeof entry !== "object") {
		return null;
	}

	const text = String(entry.text || entry.name || "").trim();
	if (!text) {
		return null;
	}

	const count = typeof entry.count === "number" ? entry.count : typeof entry.post_count === "number" ? entry.post_count : null;
	const category = normalizeDanbooruCategory(entry.category ?? entry.tag_category);
	const aliases = normalizeAliases(entry.aliases ?? entry.alias);
	return {
		text,
		source,
		count: Number.isFinite(count) ? count : null,
		category,
		aliases,
	};
}

function dedupeEntries(entries) {
	const map = new Map();
	for (const entry of entries) {
		if (!entry?.text) {
			continue;
		}
		const key = entry.text.toLowerCase();
		const prev = map.get(key);
		if (!prev) {
			map.set(key, entry);
			continue;
		}
		const prevCount = typeof prev.count === "number" ? prev.count : -1;
		const nextCount = typeof entry.count === "number" ? entry.count : -1;
		if (nextCount > prevCount) {
			map.set(key, {
				...entry,
				aliases: mergeAliases(prev.aliases, entry.aliases),
			});
			continue;
		}
		map.set(key, {
			...prev,
			aliases: mergeAliases(prev.aliases, entry.aliases),
		});
	}
	return [...map.values()];
}

function parseCustomWords(text) {
	if (!text) {
		return [];
	}
	return dedupeEntries(
		text
			.split(/[\n,]/g)
			.map((v) => normalizeEntry(v, "custom"))
			.filter(Boolean),
	);
}

function invalidateAutocompleteCaches() {
	mergedWordListCache.key = null;
	searchIndexCache.wordsRef = null;
	searchIndexCache.index = null;
}

function getDanbooruTags() {
	if (Array.isArray(danbooruTagsMemoryCache) && danbooruTagsMemoryCache.length > 0) {
		return danbooruTagsMemoryCache;
	}

	const parsed = parseJsonStorage(danbooruTagsStorageKey, []);
	if (Array.isArray(parsed) && parsed.length > 0) {
		const normalized = dedupeEntries(
			parsed
				.map((entry) => normalizeEntry(entry, "danbooru"))
				.filter(Boolean),
		);
		danbooruTagsMemoryCache = normalized;
		danbooruTagsVersion += 1;
		return normalized;
	}
	return [];
}

function setDanbooruTags(tags) {
	const serialized = tags.map((tag) => ({
		text: tag.text,
		count: tag.count,
		category: tag.category,
		aliases: normalizeAliases(tag.aliases),
	}));
	danbooruTagsMemoryCache = dedupeEntries(
		serialized
			.map((entry) => normalizeEntry(entry, "danbooru"))
			.filter(Boolean),
	);
	danbooruTagsVersion += 1;
	invalidateAutocompleteCaches();
	try {
		localStorage.setItem(danbooruTagsStorageKey, JSON.stringify(serialized));
	} catch (error) {
		console.warn("Bubba Autocomplete: localStorage quota exceeded for local tags, using in-memory cache only.", error);
		try {
			localStorage.removeItem(danbooruTagsStorageKey);
		} catch {
			// ignore cleanup errors
		}
	}
}

function setDanbooruMeta(meta) {
	localStorage.setItem(danbooruMetaStorageKey, JSON.stringify(meta));
}

function getDanbooruMeta() {
	return parseJsonStorage(danbooruMetaStorageKey, null);
}

async function loadBundledDanbooruCache() {
	const response = await fetch(LOCAL_DANBOORU_MERGED_CSV_URL, {
		cache: "no-store",
		headers: {
			"Accept": "text/csv, text/plain;q=0.9, */*;q=0.8",
		},
	});
	if (!response.ok) {
		throw new Error(`Unable to load local merged Danbooru cache (${response.status}).`);
	}
	const csvText = await response.text();
	const tags = [];
	const lines = csvText
		.split(/\r?\n/g)
		.map((line) => line.trim())
		.filter(Boolean);

	let generatedAt = null;
	let columnMap = null;

	const inferColumnMapFromRow = (rowParts) => {
		if (!Array.isArray(rowParts) || rowParts.length < 3) {
			return {
				nameIdx: 0,
				countIdx: 1,
				categoryIdx: 2,
				aliasesIdx: rowParts.length >= 4 ? 3 : -1,
			};
		}

		const second = toInt(String(rowParts[1] || "").trim(), Number.NaN);
		const third = toInt(String(rowParts[2] || "").trim(), Number.NaN);
		const secondLooksCategory = Number.isFinite(second) && second >= 0 && second <= 15;
		const thirdLooksCount = Number.isFinite(third) && third > 15;

		if (secondLooksCategory && thirdLooksCount) {
			return {
				nameIdx: 0,
				countIdx: 2,
				categoryIdx: 1,
				aliasesIdx: rowParts.length >= 4 ? 3 : -1,
			};
		}

		return {
			nameIdx: 0,
			countIdx: 1,
			categoryIdx: 2,
			aliasesIdx: rowParts.length >= 4 ? 3 : -1,
		};
	};

	for (const line of lines) {
		if (line.startsWith("#")) {
			const match = line.slice(1).trim().match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/);
			if (!match) {
				continue;
			}
			const key = match[1];
			const value = match[2];
			if (key === "generated_at") {
				generatedAt = value;
			}
			continue;
		}

		const header = line.toLowerCase();
		if (header.startsWith("tag,") || header.startsWith("name,")) {
			const cols = parseCsvRow(line).map((part) => String(part || "").trim().toLowerCase());
			const nameIdx = cols.indexOf("tag") >= 0 ? cols.indexOf("tag") : cols.indexOf("name");
			const countIdx = cols.indexOf("post_count") >= 0 ? cols.indexOf("post_count") : cols.indexOf("count");
			const categoryIdx = cols.indexOf("category") >= 0 ? cols.indexOf("category") : cols.indexOf("type");
			const aliasesIdx = cols.indexOf("aliases") >= 0 ? cols.indexOf("aliases") : cols.indexOf("alias");

			columnMap = {
				nameIdx: nameIdx >= 0 ? nameIdx : 0,
				countIdx: countIdx >= 0 ? countIdx : 1,
				categoryIdx,
				aliasesIdx,
			};
			continue;
		}
		const parts = parseCsvRow(line);
		if (parts.length < 2) {
			continue;
		}
		if (!columnMap) {
			columnMap = inferColumnMapFromRow(parts);
		}

		const nameIdx = columnMap?.nameIdx ?? 0;
		const countIdx = columnMap?.countIdx ?? 1;
		const categoryIdx = Number.isInteger(columnMap?.categoryIdx) ? columnMap.categoryIdx : 2;
		const aliasesIdx = Number.isInteger(columnMap?.aliasesIdx) ? columnMap.aliasesIdx : 3;

		const tag = String(parts[nameIdx] || "").trim();
		const count = Math.max(0, toInt(String(parts[countIdx] || "0").trim(), 0));
		const category = categoryIdx >= 0 ? normalizeDanbooruCategory(String(parts[categoryIdx] || "").trim()) : null;
		const aliases = aliasesIdx >= 0 ? String(parts[aliasesIdx] || "").trim() : "";
		const entry = normalizeEntry({ name: tag, count, category, aliases }, "danbooru");
		if (entry) {
			tags.push(entry);
		}
	}

	return {
		tags,
		meta: {
			seedSource: "upstream",
			schemaVersion: bundledCacheSchemaVersion,
			generatedAt,
		},
	};
}

async function ensureLocalCsvCacheSeeded() {
	const existing = getDanbooruTags();
	if (existing.length > 0) {
		const hasAliasData = existing.some((entry) => Array.isArray(entry?.aliases) && entry.aliases.length > 0);
		const hasSwappedData = hasLikelySwappedCountCategory(existing);
		if (hasAliasData && !hasSwappedData) {
			return;
		}
	}

	try {
		const bundled = await loadBundledDanbooruCache();
		if (!bundled.tags.length) {
			return;
		}
		setDanbooruTags(bundled.tags);
		setDanbooruMeta({
			updatedAt: new Date().toISOString(),
			count: bundled.tags.length,
			seedSource: bundled.meta.seedSource,
			schemaVersion: bundled.meta.schemaVersion,
			bundledGeneratedAt: bundled.meta.generatedAt,
			fetchMode: "local-csv",
			sourceUrl: String(LOCAL_DANBOORU_MERGED_CSV_URL),
		});
	} catch (error) {
		console.warn("Bubba Autocomplete: failed to load local merged Danbooru cache", error);
	}
}

async function fetchLocalCsvTags() {
	const bundled = await loadBundledDanbooruCache();
	const tags = bundled.tags
		.slice()
		.sort((a, b) => {
			const aCount = typeof a.count === "number" ? a.count : -1;
			const bCount = typeof b.count === "number" ? b.count : -1;
			if (bCount !== aCount) {
				return bCount - aCount;
			}
			return a.text.localeCompare(b.text);
		});

	return {
		tags,
		truncated: false,
		mode: "local-csv",
	};
}

function parseLocalTagCacheStatus() {
	const meta = getDanbooruMeta();
	if (!meta || !meta.updatedAt) {
		return "No local tag cache loaded.";
	}
	const date = new Date(meta.updatedAt);
	const dateText = Number.isNaN(date.getTime()) ? String(meta.updatedAt) : date.toLocaleString();
	const countText = typeof meta.count === "number" ? formatNumber(meta.count) : "0";
	const details = [];
	if (meta.fetchMode) {
		details.push(`mode ${meta.fetchMode}`);
	}
	if (meta.seedSource) {
		details.push(`source ${meta.seedSource}`);
	}
	if (meta.truncated) {
		details.push("truncated");
	}
	const detailText = details.length ? ` (${details.join(", ")})` : "";
	return `Cached ${countText} local tags${detailText}. Updated ${dateText}.`;
}

function getWordList() {
	const customRaw = localStorage.getItem(customWordsStorageKey) || "";
	const cacheKey = `1|${danbooruTagsVersion}|${customRaw}`;
	if (mergedWordListCache.key === cacheKey && Array.isArray(mergedWordListCache.words)) {
		return mergedWordListCache.words;
	}

	const words = [];
	for (const item of parseCustomWords(customRaw)) {
		words.push(item);
	}
	for (const item of getDanbooruTags()) {
		words.push(item);
	}

	const deduped = dedupeEntries(words);
	mergedWordListCache = {
		key: cacheKey,
		words: deduped,
	};
	invalidateAutocompleteCaches();
	return deduped;
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

function buildSearchIndex(words) {
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

		const keys = [textNorm, textCompact, ...aliasNorm, ...aliasCompact].filter(Boolean);
		for (const key of keys) {
			addIndexBucket(prefixBuckets, key.slice(0, 1), i);
			addIndexBucket(prefixBuckets, key.slice(0, 2), i);
			addIndexBucket(prefixBuckets, key.slice(0, 3), i);
		}
	}

	return {
		entries,
		prefixBuckets,
	};
}

function getSearchIndex(words) {
	if (searchIndexCache.wordsRef === words && searchIndexCache.index) {
		return searchIndexCache.index;
	}
	const index = buildSearchIndex(words);
	searchIndexCache.wordsRef = words;
	searchIndexCache.index = index;
	return index;
}

function scoreTextMatch(rawText, queryVariations) {
	const text = String(rawText || "").toLowerCase();
	if (!text || !queryVariations.length) {
		return 0;
	}

	const normalizedText = normalizeSearchText(text);
	const compactText = normalizedText.replace(/\s+/g, "");
	const preparedQueries = buildPreparedQueries(queryVariations);
	return scorePreparedText(normalizedText, compactText, preparedQueries);
}

function scorePreparedText(normText, compactText, preparedQueries) {
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

function buildPreparedQueries(queryVariations) {
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

function findMatchesFromIndex(index, queryVariations) {
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

function hasLikelySwappedCountCategory(entries) {
	if (!Array.isArray(entries) || !entries.length) {
		return false;
	}

	const sampleSize = Math.min(entries.length, 500);
	let checked = 0;
	let suspicious = 0;

	for (let i = 0; i < sampleSize; i += 1) {
		const entry = entries[i];
		if (typeof entry?.count !== "number" || typeof entry?.category !== "number") {
			continue;
		}
		checked += 1;
		if (entry.count <= 20 && entry.category > 1000) {
			suspicious += 1;
		}
	}

	if (checked < 25) {
		return false;
	}

	return suspicious / checked >= 0.3;
}

function findMatchMetadata(item, queryVariations) {
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

class BubbaTextAutoComplete {
	constructor(inputEl, group) {
		this.inputEl = inputEl;
		this.group = group || "common";
		this.menuEl = document.createElement("div");
		this.menuEl.classList.add("bubba-autocomplete");
		document.body.appendChild(this.menuEl);
		this.menuEl.style.display = "none";
		this.items = [];
		this.selectedIndex = -1;
		this.searchDebounceMs = 20;
		this.searchTimer = null;
		this.previousQuery = "";
		this.previousMatchedPool = null;

		this.onInput = this.onInput.bind(this);
		this.onInputImmediate = this.onInputImmediate.bind(this);
		this.onKeyDown = this.onKeyDown.bind(this);
		this.onBlur = this.onBlur.bind(this);
		this.onFocus = this.onFocus.bind(this);

		this.inputEl.addEventListener("input", this.onInput);
		this.inputEl.addEventListener("keydown", this.onKeyDown);
		this.inputEl.addEventListener("blur", this.onBlur);
		this.inputEl.addEventListener("focus", this.onFocus);
	}

	getTokenStart(value, caret) {
		const comma = value.lastIndexOf(",", caret - 1);
		const newline = value.lastIndexOf("\n", caret - 1);
		return Math.max(comma, newline) + 1;
	}

	getQuery() {
		const value = this.inputEl.value;
		const caret = this.inputEl.selectionStart ?? value.length;
		const tokenStart = this.getTokenStart(value, caret);
		const raw = value.slice(tokenStart, caret);
		return {
			caret,
			tokenStart,
			raw,
			query: raw.trim().toLowerCase(),
		};
	}

	show(items) {
		if (!items.length) {
			this.hide();
			return;
		}

		this.items = items;
		this.selectedIndex = 0;
		this.menuEl.replaceChildren();
		for (let i = 0; i < items.length; i += 1) {
			const item = items[i];
			const row = document.createElement("div");
			row.classList.add("bubba-autocomplete-item");
			row.onmousedown = (event) => {
				event.preventDefault();
				this.insert(item);
			};
			this.menuEl.appendChild(row);
			const textSpan = document.createElement("span");
			textSpan.textContent = item.text;
			row.appendChild(textSpan);
			if (typeof item.count === "number") {
				const categoryLabel = getDanbooruCategoryLabel(item.category);
				const metaText = categoryLabel ? `${formatNumber(item.count)} | ${categoryLabel}` : formatNumber(item.count);
				const metaSpan = document.createElement("span");
				metaSpan.classList.add("bubba-autocomplete-item-meta");
				metaSpan.textContent = metaText;
				row.appendChild(metaSpan);
			}
			if (item.matchedAlias) {
				const altSpan = document.createElement("span");
				altSpan.classList.add("bubba-autocomplete-item-alt");
				altSpan.textContent = `<- ${item.matchedAlias}`;
				row.appendChild(altSpan);
			}
			if (i === 0) {
				row.classList.add("selected");
			}
		}

		const rect = this.inputEl.getBoundingClientRect();
		this.menuEl.style.left = `${Math.round(rect.left)}px`;
		this.menuEl.style.top = `${Math.round(rect.bottom + 4)}px`;
		this.menuEl.style.width = `${Math.max(220, Math.round(rect.width))}px`;
		this.menuEl.style.display = "block";
	}

	hide() {
		this.items = [];
		this.selectedIndex = -1;
		this.menuEl.style.display = "none";
	}

	setSelected(index) {
		if (!this.items.length) return;
		this.selectedIndex = (index + this.items.length) % this.items.length;
		const rows = this.menuEl.querySelectorAll(".bubba-autocomplete-item");
		for (let i = 0; i < rows.length; i += 1) {
			rows[i].classList.toggle("selected", i === this.selectedIndex);
		}
		rows[this.selectedIndex]?.scrollIntoView({ block: "nearest" });
	}

	insert(item) {
		if (!item?.text) {
			return;
		}
		const text = item.text;
		const value = this.inputEl.value;
		const caret = this.inputEl.selectionStart ?? value.length;
		const { tokenStart, raw } = this.getQuery();
		const leadingSpaces = raw.match(/^\s*/)?.[0] || "";
		const before = value.slice(0, tokenStart);
		const after = value.slice(caret);
		const needsComma = !after.trimStart().startsWith(",");
		const insertion = `${leadingSpaces}${text}${needsComma ? ", " : ""}`;
		const nextValue = `${before}${insertion}${after}`;
		const nextCaret = before.length + insertion.length;

		this.inputEl.value = nextValue;
		this.inputEl.setSelectionRange(nextCaret, nextCaret);
		this.inputEl.dispatchEvent(new Event("input", { bubbles: true }));
		this.hide();
	}

	getMatchBucket(matchScore) {
		const score = Number.isFinite(matchScore) ? matchScore : 0;
		if (score >= 850) {
			return 3;
		}
		if (score >= 700) {
			return 2;
		}
		if (score > 0) {
			return 1;
		}
		return 0;
	}

	onInput() {
		if (this.searchTimer) {
			clearTimeout(this.searchTimer);
			this.searchTimer = null;
		}
		this.searchTimer = setTimeout(this.onInputImmediate, this.searchDebounceMs);
	}

	onInputImmediate() {
		if (!BubbaTextAutoComplete.enabled) {
			this.hide();
			return;
		}
		const { query } = this.getQuery();
		if (!query) {
			this.previousQuery = "";
			this.previousMatchedPool = null;
			this.hide();
			return;
		}
		const queryVariations = getSearchQueryVariations(query);
		const words = getWordList();
		const index = getSearchIndex(words);

		let candidatePool = null;
		if (
			this.previousQuery &&
			query.startsWith(this.previousQuery) &&
			Array.isArray(this.previousMatchedPool) &&
			this.previousMatchedPool.length > 0
		) {
			candidatePool = this.previousMatchedPool;
		}

		const matched = (candidatePool
			? candidatePool
					.map((item) => {
						const match = findMatchMetadata(item, queryVariations);
						if (!match) {
							return null;
						}
						return {
							...item,
							matchScore: match.score,
							matchedAlias: match.matchedAlias,
						};
					})
					.filter(Boolean)
			: findMatchesFromIndex(index, queryVariations)
		)
			.sort((a, b) => {
				const aBucket = this.getMatchBucket(a.matchScore);
				const bBucket = this.getMatchBucket(b.matchScore);
				if (bBucket !== aBucket) {
					return bBucket - aBucket;
				}
				const aCount = typeof a.count === "number" ? a.count : -1;
				const bCount = typeof b.count === "number" ? b.count : -1;
				if (bCount !== aCount) {
					return bCount - aCount;
				}
				const aScore = Number.isFinite(a.matchScore) ? a.matchScore : 0;
				const bScore = Number.isFinite(b.matchScore) ? b.matchScore : 0;
				if (bScore !== aScore) {
					return bScore - aScore;
				}
				return a.text.localeCompare(b.text);
			});

		this.previousQuery = query;
		this.previousMatchedPool = matched;

		const results = matched.slice(0, BubbaTextAutoComplete.suggestionLimit);

		this.show(results);
	}

	onFocus() {
		if (!BubbaTextAutoComplete.enabled) return;
		this.onInputImmediate();
	}

	onBlur() {
		if (this.searchTimer) {
			clearTimeout(this.searchTimer);
			this.searchTimer = null;
		}
		setTimeout(() => this.hide(), 100);
	}

	onKeyDown(event) {
		if (this.menuEl.style.display !== "block") {
			return;
		}
		if (event.key === "ArrowDown") {
			event.preventDefault();
			this.setSelected(this.selectedIndex + 1);
			return;
		}
		if (event.key === "ArrowUp") {
			event.preventDefault();
			this.setSelected(this.selectedIndex - 1);
			return;
		}
		if (event.key === "Tab" || event.key === "Enter") {
			event.preventDefault();
			if (this.selectedIndex >= 0 && this.items[this.selectedIndex]) {
				this.insert(this.items[this.selectedIndex]);
			}
			return;
		}
		if (event.key === "Escape") {
			event.preventDefault();
			this.hide();
		}
	}
}

BubbaTextAutoComplete.enabled = true;
BubbaTextAutoComplete.suggestionLimit = 15;

function resolveGroup(node, inputName, inputData) {
	const config = inputData?.[1]?.["bubba.autocomplete"];
	if (config === false) {
		return null;
	}
	if (typeof config === "object" && typeof config.group === "string") {
		return config.group;
	}
	if (typeof inputName === "string") {
		return inputName;
	}
	if ((node?.comfyClass || "").toLowerCase().includes("prompt")) {
		return "common";
	}
	return null;
}

function installStringWidgetHook() {
	const original = ComfyWidgets.STRING;
	if (original.__bubbaAutoCompletePatched) {
		return;
	}

	ComfyWidgets.STRING = function (node, inputName, inputData) {
		const result = original.apply(this, arguments);
		const options = inputData?.[1] || {};
		if (!options.multiline) {
			return result;
		}

		const className = node?.comfyClass || "";
		if (!className.startsWith("Bubba")) {
			return result;
		}

		const group = resolveGroup(node, inputName, inputData);
		if (!group) {
			return result;
		}

		const inputEl = result?.widget?.inputEl || result?.widget?.element;
		if (!inputEl || inputEl.dataset.bubbaAutocompleteAttached === "1") {
			return result;
		}

		inputEl.dataset.bubbaAutocompleteAttached = "1";
		new BubbaTextAutoComplete(inputEl, group);
		return result;
	};

	ComfyWidgets.STRING.__bubbaAutoCompletePatched = true;
}

function buildLocalTagCacheCsvLines(tags, meta = {}) {
	const generatedAt = new Date().toISOString();
	void meta;

	const lines = [
		`# schema_version=${bundledCacheSchemaVersion}`,
		"# source=danbooru",
		`# generated_at=${generatedAt}`,
		`# tag_count=${tags.length}`,
		"tag,count,category,aliases",
	];

	for (const tag of tags) {
		const text = String(tag.text || "").replace(/\r?\n/g, " ").trim();
		if (!text) {
			continue;
		}
		const count = typeof tag.count === "number" ? tag.count : 0;
		const category = normalizeDanbooruCategory(tag.category);
		const aliases = normalizeAliases(tag.aliases).join(",");
		lines.push(`${toCsvField(text)},${count},${category ?? ""},${toCsvField(aliases)}`);
	}

	return lines;
}

function exportLocalTagCacheCsv() {
	const tags = getDanbooruTags();
	if (!tags.length) {
		alert("Bubba Autocomplete: no local tag cache available to export.");
		return;
	}

	const meta = getDanbooruMeta() || {};
	const lines = buildLocalTagCacheCsvLines(tags, meta);

	const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = "danbooru_e621_merged.csv";
	a.style.display = "none";
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

async function refreshLocalCsvCache(buttonEl) {
	if (buttonEl) {
		buttonEl.disabled = true;
		buttonEl.textContent = "Downloading...";
	}

	try {
		const syncResponse = await fetch("/bubba/sync_upstream_cache", {
			method: "POST",
			cache: "no-store",
		});
		if (!syncResponse.ok) {
			let message = `HTTP ${syncResponse.status}`;
			try {
				const payload = await syncResponse.json();
				if (payload?.error) {
					message = String(payload.error);
				}
			} catch {
				// ignore parse failures
			}
			throw new Error(`Failed to sync local CSV from upstream: ${message}`);
		}

		if (buttonEl) {
			buttonEl.textContent = "Refreshing...";
		}

		const result = await fetchLocalCsvTags();
		const nextMeta = {
			updatedAt: new Date().toISOString(),
			count: result.tags.length,
			fetchMode: result.mode,
			truncated: result.truncated,
			seedSource: "local",
			sourceUrl: String(LOCAL_DANBOORU_MERGED_CSV_URL),
			schemaVersion: bundledCacheSchemaVersion,
		};
		setDanbooruTags(result.tags);
		setDanbooruMeta(nextMeta);
		alert(`Bubba Autocomplete: Cached ${formatNumber(result.tags.length)} tags from local merged CSV.`);
	} catch (error) {
		console.error(error);
		alert(`Bubba Autocomplete: Failed to refresh local CSV. ${error?.message || "Unknown error"}`);
	} finally {
		if (buttonEl) {
			buttonEl.disabled = false;
			buttonEl.textContent = "Download Latest + Rebuild Cache";
		}
	}
}

function clearLocalTagCache() {
	localStorage.removeItem(danbooruTagsStorageKey);
	localStorage.removeItem(danbooruMetaStorageKey);
	danbooruTagsMemoryCache = [];
	danbooruTagsVersion += 1;
	invalidateAutocompleteCaches();
}

export {
	BubbaTextAutoComplete,
	installStringWidgetHook,
	ensureLocalCsvCacheSeeded,
	exportLocalTagCacheCsv,
	refreshLocalCsvCache,
	clearLocalTagCache,
	parseLocalTagCacheStatus,
};
