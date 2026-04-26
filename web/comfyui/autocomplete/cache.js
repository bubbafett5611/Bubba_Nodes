// Cache management for Danbooru tags and embeddings

import { normalizeEntry, dedupeEntries, parseCustomWords, normalizeAliases, parseJsonStorage } from './utils.js';
import { invalidateSearchIndexCache } from './search.js';
import { loadDanbooruTagsFromIndexedDb, saveDanbooruTagsToIndexedDb, clearDanbooruTagsFromIndexedDb } from './idb.js';

const customWordsStorageKey = "bubba.Autocomplete.CustomWords";
const danbooruTagsStorageKey = "bubba.Autocomplete.DanbooruTags";
const danbooruMetaStorageKey = "bubba.Autocomplete.DanbooruMeta";
const embeddingsStorageKey = "bubba.Autocomplete.Embeddings";
const embeddingsMetaStorageKey = "bubba.Autocomplete.EmbeddingsMeta";

let danbooruTagsMemoryCache = [];
let danbooruTagsVersion = 0;
let embeddingsMemoryCache = [];
let embeddingsVersion = 0;
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

export function getWordList() {
	const customRaw = localStorage.getItem(customWordsStorageKey) || "";
	const cacheKey = `1|${danbooruTagsVersion}|${embeddingsVersion}|${customRaw}`;
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
	for (const item of getEmbeddingEntries()) {
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
	danbooruTags: danbooruTagsStorageKey,
	danbooruMeta: danbooruMetaStorageKey,
	embeddings: embeddingsStorageKey,
	embeddingsMeta: embeddingsMetaStorageKey,
};
