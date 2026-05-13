import { buildSearchIndex, findMatchesFromIndex } from "./search.js";

let currentWords = null;
let currentIndex = null;

function compareMatches(a, b) {
	const aScore = Number.isFinite(a.matchScore) ? a.matchScore : 0;
	const bScore = Number.isFinite(b.matchScore) ? b.matchScore : 0;
	const aBucket = aScore >= 850 ? 3 : aScore >= 700 ? 2 : aScore > 0 ? 1 : 0;
	const bBucket = bScore >= 850 ? 3 : bScore >= 700 ? 2 : bScore > 0 ? 1 : 0;
	if (aBucket !== bBucket) {
		return bBucket - aBucket;
	}
	const aPriority = Number.isFinite(a.matchPriority) ? a.matchPriority : 0;
	const bPriority = Number.isFinite(b.matchPriority) ? b.matchPriority : 0;
	if (aPriority !== bPriority) {
		return bPriority - aPriority;
	}
	const aCount = typeof a.count === "number" ? a.count : -1;
	const bCount = typeof b.count === "number" ? b.count : -1;
	if (aCount !== bCount) {
		return bCount - aCount;
	}
	if (aScore !== bScore) {
		return bScore - aScore;
	}
	return String(a.text || "").localeCompare(String(b.text || ""));
}

function selectTopMatches(matched, limit) {
	if (!Array.isArray(matched) || limit <= 0 || matched.length === 0) {
		return [];
	}

	const hasCanonicalExactMatch = matched.some((item) => item?.matchKind === "exact" && !item?.matchedAlias);
	const top = [];
	for (const item of matched) {
		if (hasCanonicalExactMatch && item?.matchedAlias) {
			continue;
		}
		let inserted = false;
		for (let i = 0; i < top.length; i += 1) {
			if (compareMatches(item, top[i]) < 0) {
				top.splice(i, 0, item);
				inserted = true;
				break;
			}
		}
		if (!inserted && top.length < limit) {
			top.push(item);
			inserted = true;
		}
		if (inserted && top.length > limit) {
			top.pop();
		}
	}

	return top;
}

self.onmessage = (event) => {
	const message = event?.data || {};
	const { type, requestId } = message;

	try {
		if (type === "syncWords") {
			const words = Array.isArray(message.words) ? message.words : [];
			if (currentWords !== words) {
				currentWords = words;
				currentIndex = buildSearchIndex(words);
			}
			self.postMessage({
				type: "syncAck",
				requestId,
				entryCount: currentIndex?.entries?.length || 0,
			});
			return;
		}

		if (type === "query") {
			if (!currentIndex) {
				self.postMessage({
					type: "queryResult",
					requestId,
					results: [],
				});
				return;
			}

			const queryVariations = Array.isArray(message.queryVariations) ? message.queryVariations : [];
			const limit = Math.max(1, Number.parseInt(String(message.limit || 20), 10) || 20);
			const matched = findMatchesFromIndex(currentIndex, queryVariations);
			const results = selectTopMatches(matched, limit);
			self.postMessage({
				type: "queryResult",
				requestId,
				results,
			});
		}
	} catch (error) {
		self.postMessage({
			type: "error",
			requestId,
			error: String(error?.message || error || "worker_error"),
		});
	}
};
