// Cache management for Danbooru tags and embeddings

import { normalizeEntry, dedupeEntries, parseCustomWords, normalizeAliases, parseJsonStorage } from './utils.js';
import { invalidateSearchIndexCache } from './search.js';
import { loadDanbooruTagsFromIndexedDb, saveDanbooruTagsToIndexedDb, clearDanbooruTagsFromIndexedDb } from './idb.js';

const customWordsStorageKey = "bubba.Autocomplete.CustomWords";
const includeLocalCsvTagsStorageKey = "bubba.Autocomplete.IncludeLocalCsvTags";
const danbooruTagsStorageKey = "bubba.Autocomplete.DanbooruTags";
const danbooruMetaStorageKey = "bubba.Autocomplete.DanbooruMeta";
const embeddingsStorageKey = "bubba.Autocomplete.Embeddings";
const embeddingsMetaStorageKey = "bubba.Autocomplete.EmbeddingsMeta";
const wildcardsStorageKey = "bubba.Autocomplete.Wildcards";
const wildcardsMetaStorageKey = "bubba.Autocomplete.WildcardsMeta";

let danbooruTagsMemoryCache = [];
let danbooruTagsVersion = 0;
let embeddingsMemoryCache = [];
let embeddingsVersion = 0;
let wildcardsMemoryCache = [];
let wildcardRefreshPromise = null;
let wildcardRefreshAttempted = false;
let danbooruHydrationPromise = null;
let mergedWordListCache = {
	key: null,
	words: [],
};

function normalizeDanbooruEntries(raw) {
	return dedupeEntries(
		(raw || [])
			.map((entry) => normalizeEntry(entry, "danbooru"))
			.filter(Boolean),
	);
}

export function getDanbooruTags() {
	if (Array.isArray(danbooruTagsMemoryCache) && danbooruTagsMemoryCache.length > 0) {
		return danbooruTagsMemoryCache;
	}

	const parsed = parseJsonStorage(danbooruTagsStorageKey, []);
	if (Array.isArray(parsed) && parsed.length > 0) {
		const normalized = normalizeDanbooruEntries(parsed);
		danbooruTagsMemoryCache = normalized;
		danbooruTagsVersion += 1;
		return normalized;
	}
	return [];
}

export async function hydrateDanbooruTagsFromPersistentCache() {
	if (Array.isArray(danbooruTagsMemoryCache) && danbooruTagsMemoryCache.length > 0) {
		return danbooruTagsMemoryCache;
	}

	if (danbooruHydrationPromise) {
		return danbooruHydrationPromise;
	}

	danbooruHydrationPromise = (async () => {
		const localParsed = parseJsonStorage(danbooruTagsStorageKey, []);
		if (Array.isArray(localParsed) && localParsed.length > 0) {
			const normalized = normalizeDanbooruEntries(localParsed);
			danbooruTagsMemoryCache = normalized;
			danbooruTagsVersion += 1;
			// Migrate legacy localStorage payload to IndexedDB.
			saveDanbooruTagsToIndexedDb(localParsed).catch((error) => {
				console.warn("Bubba Autocomplete: failed to migrate local tags into IndexedDB", error);
			});
			try {
				localStorage.removeItem(danbooruTagsStorageKey);
			} catch {
				// ignore cleanup errors
			}
			return normalized;
		}

		const indexedDbTags = await loadDanbooruTagsFromIndexedDb();
		if (Array.isArray(indexedDbTags) && indexedDbTags.length > 0) {
			const normalized = normalizeDanbooruEntries(indexedDbTags);
			danbooruTagsMemoryCache = normalized;
			danbooruTagsVersion += 1;
			return normalized;
		}

		return [];
	})().finally(() => {
		danbooruHydrationPromise = null;
	});

	return danbooruHydrationPromise;
}

export function setDanbooruTags(tags) {
	const serialized = tags.map((tag) => ({
		text: tag.text,
		source: tag.source,
		sources: tag.sources,
		count: tag.count,
		category: tag.category,
		aliases: normalizeAliases(tag.aliases),
	}));
	danbooruTagsMemoryCache = normalizeDanbooruEntries(serialized);
	danbooruTagsVersion += 1;
	invalidateAutocompleteCaches();
	saveDanbooruTagsToIndexedDb(serialized).catch((error) => {
		console.warn("Bubba Autocomplete: failed to persist local tags to IndexedDB", error);
	});
	try {
		localStorage.removeItem(danbooruTagsStorageKey);
	} catch {
		// ignore cleanup errors
	}
}

export function setDanbooruMeta(meta) {
	localStorage.setItem(danbooruMetaStorageKey, JSON.stringify(meta));
}

export function getDanbooruMeta() {
	return parseJsonStorage(danbooruMetaStorageKey, null);
}

export function getEmbeddingsMeta() {
	return parseJsonStorage(embeddingsMetaStorageKey, null);
}

export function setEmbeddingsMeta(meta) {
	localStorage.setItem(embeddingsMetaStorageKey, JSON.stringify(meta));
}

export function getEmbeddingEntries() {
	if (Array.isArray(embeddingsMemoryCache) && embeddingsMemoryCache.length > 0) {
		return embeddingsMemoryCache;
	}

	const parsed = parseJsonStorage(embeddingsStorageKey, []);
	if (Array.isArray(parsed) && parsed.length > 0) {
		const normalized = dedupeEntries(
			parsed
				.map((entry) => normalizeEntry(entry, "embedding"))
				.filter(Boolean),
		);
		embeddingsMemoryCache = normalized;
		embeddingsVersion += 1;
		return normalized;
	}

	return [];
}

export function setEmbeddingEntries(entries) {
	const serialized = (entries || []).map((entry) => ({
		text: String(entry?.text || "").trim(),
		aliases: normalizeAliases(entry?.aliases),
	}));

	embeddingsMemoryCache = dedupeEntries(
		serialized
			.map((entry) => normalizeEntry(entry, "embedding"))
			.filter(Boolean),
	);
	embeddingsVersion += 1;
	invalidateAutocompleteCaches();

	try {
		localStorage.setItem(embeddingsStorageKey, JSON.stringify(serialized));
	} catch (error) {
		console.warn("Bubba Autocomplete: localStorage quota exceeded for embeddings cache, using in-memory cache only.", error);
		try {
			localStorage.removeItem(embeddingsStorageKey);
		} catch {
			// ignore cleanup errors
		}
	}
}

export async function refreshEmbeddingCacheFromServer() {
	const response = await fetch("/bubba/autocomplete/embeddings", {
		cache: "no-store",
		headers: {
			"Accept": "application/json",
		},
	});

	if (!response.ok) {
		throw new Error(`Unable to load embeddings (${response.status}).`);
	}

	const payload = await response.json();
	const embeddings = Array.isArray(payload?.embeddings) ? payload.embeddings : [];
	setEmbeddingEntries(embeddings);
	setEmbeddingsMeta({
		updatedAt: new Date().toISOString(),
		count: embeddings.length,
		status: String(payload?.status || "ok"),
	});
}

export async function ensureEmbeddingCacheSeeded() {
	const existing = getEmbeddingEntries();
	if (existing.length > 0) {
		return false;
	}

	const meta = getEmbeddingsMeta();
	if (meta?.status === "folder_paths_unavailable") {
		return false;
	}

	try {
		await refreshEmbeddingCacheFromServer();
		return true;
	} catch (error) {
		console.warn("Bubba Autocomplete: failed to load embeddings for autocomplete", error);
		return false;
	}
}

function normalizeWildcardEntry(entry) {
	const path = String(entry?.text || entry?.name || "").trim().replace(/^__|__$/g, "");
	if (!path) {
		return null;
	}
	return {
		kind: "wildcard",
		text: `__${path}__`,
		insertText: String(entry?.insert_text || `__${path}__`),
		path,
		source: "wildcard",
	};
}

export function getWildcardEntries() {
	if (wildcardsMemoryCache.length > 0) {
		return wildcardsMemoryCache;
	}
	const parsed = parseJsonStorage(wildcardsStorageKey, []);
	if (!Array.isArray(parsed)) {
		return [];
	}
	wildcardsMemoryCache = parsed.map(normalizeWildcardEntry).filter(Boolean);
	return wildcardsMemoryCache;
}

export function setWildcardEntries(entries) {
	const normalized = (entries || []).map(normalizeWildcardEntry).filter(Boolean);
	const deduped = new Map();
	for (const entry of normalized) {
		deduped.set(entry.path.toLowerCase(), entry);
	}
	wildcardsMemoryCache = [...deduped.values()].sort((left, right) => left.path.localeCompare(right.path));
	localStorage.setItem(wildcardsStorageKey, JSON.stringify(wildcardsMemoryCache));
}

export async function refreshWildcardCacheFromServer() {
	const response = await fetch("/bubba/autocomplete/wildcards", {
		cache: "no-store",
		headers: {
			"Accept": "application/json",
		},
	});
	if (!response.ok) {
		throw new Error(`Unable to load wildcards (${response.status}).`);
	}
	const payload = await response.json();
	const wildcards = Array.isArray(payload?.wildcards) ? payload.wildcards : [];
	setWildcardEntries(wildcards);
	localStorage.setItem(wildcardsMetaStorageKey, JSON.stringify({
		updatedAt: new Date().toISOString(),
		count: wildcards.length,
		status: String(payload?.status || "ok"),
	}));
}

export async function ensureWildcardCacheSeeded() {
	if (wildcardRefreshPromise) {
		return wildcardRefreshPromise;
	}
	if (wildcardRefreshAttempted) {
		return false;
	}
	wildcardRefreshAttempted = true;
	wildcardRefreshPromise = refreshWildcardCacheFromServer()
		.then(() => true)
		.catch((error) => {
			console.warn("Bubba Autocomplete: failed to load wildcards for autocomplete", error);
			return false;
		})
		.finally(() => {
			wildcardRefreshPromise = null;
		});
	return wildcardRefreshPromise;
}

export function findWildcardMatches(query, limit = 20) {
	const normalizedQuery = String(query || "").trim().toLowerCase().replace(/^__/, "").replace(/__$/, "");
	const matches = getWildcardEntries().filter((entry) => {
		if (!normalizedQuery) {
			return true;
		}
		return entry.path.toLowerCase().includes(normalizedQuery);
	});
	matches.sort((left, right) => {
		const leftPath = left.path.toLowerCase();
		const rightPath = right.path.toLowerCase();
		const leftPrefix = normalizedQuery && leftPath.startsWith(normalizedQuery) ? 0 : 1;
		const rightPrefix = normalizedQuery && rightPath.startsWith(normalizedQuery) ? 0 : 1;
		if (leftPrefix !== rightPrefix) {
			return leftPrefix - rightPrefix;
		}
		return leftPath.localeCompare(rightPath);
	});
	return matches.slice(0, Math.max(1, Number(limit) || 20));
}

export function getWordList() {
	const customRaw = localStorage.getItem(customWordsStorageKey) || "";
	const includeLocalCsvTags = localStorage.getItem(includeLocalCsvTagsStorageKey) !== "false";
	const cacheKey = `1|${danbooruTagsVersion}|${embeddingsVersion}|${includeLocalCsvTags}|${customRaw}`;
	if (mergedWordListCache.key === cacheKey && Array.isArray(mergedWordListCache.words)) {
		return mergedWordListCache.words;
	}

	const words = [];
	for (const item of parseCustomWords(customRaw)) {
		words.push(item);
	}
	if (includeLocalCsvTags) {
		for (const item of getDanbooruTags()) {
			words.push(item);
		}
	}
	for (const item of getEmbeddingEntries()) {
		words.push(item);
	}

	const deduped = dedupeEntries(words);
	mergedWordListCache = {
		key: cacheKey,
		words: deduped,
	};
	invalidateSearchIndexCache();
	return deduped;
}

function invalidateAutocompleteCaches() {
	mergedWordListCache.key = null;
	mergedWordListCache.words = [];
	invalidateSearchIndexCache();
}

export function clearDanbooruCache() {
	danbooruTagsMemoryCache = [];
	danbooruTagsVersion += 1;
	invalidateAutocompleteCaches();
}

export function clearDanbooruPersistentCache() {
	clearDanbooruTagsFromIndexedDb().catch((error) => {
		console.warn("Bubba Autocomplete: failed to clear persistent Danbooru cache", error);
	});
	try {
		localStorage.removeItem(danbooruTagsStorageKey);
	} catch {
		// ignore cleanup errors
	}
}

export const cacheStorageKeys = {
	customWords: customWordsStorageKey,
	includeLocalCsvTags: includeLocalCsvTagsStorageKey,
	danbooruTags: danbooruTagsStorageKey,
	danbooruMeta: danbooruMetaStorageKey,
	embeddings: embeddingsStorageKey,
	embeddingsMeta: embeddingsMetaStorageKey,
	wildcards: wildcardsStorageKey,
	wildcardsMeta: wildcardsMetaStorageKey,
};
