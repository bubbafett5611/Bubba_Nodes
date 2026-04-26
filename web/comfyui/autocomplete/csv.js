// CSV parsing and Danbooru tag loading

import { toInt, normalizeDanbooruCategory, normalizeEntry, parseCsvRow, toCsvField, hasLikelySwappedCountCategory, formatNumber } from './utils.js';
import { getDanbooruTags, setDanbooruTags, setDanbooruMeta, getDanbooruMeta, cacheStorageKeys, clearDanbooruCache, hydrateDanbooruTagsFromPersistentCache, clearDanbooruPersistentCache } from './cache.js';

const bundledCacheSchemaVersion = 1;
const LOCAL_DANBOORU_MERGED_CSV_URL = new URL("../danbooru_e621_merged.csv", import.meta.url);

export async function loadBundledDanbooruCache() {
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

export async function ensureLocalCsvCacheSeeded() {
	await hydrateDanbooruTagsFromPersistentCache();
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

export async function fetchLocalCsvTags() {
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

export function parseLocalTagCacheStatus() {
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

export function buildLocalTagCacheCsvLines(tags, meta = {}) {
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
		const aliases = (tag.aliases || []).join(",");
		lines.push(`${toCsvField(text)},${count},${category ?? ""},${toCsvField(aliases)}`);
	}

	return lines;
}

export function exportLocalTagCacheCsv() {
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

export async function refreshLocalCsvCache(buttonEl) {
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

export function clearLocalTagCache() {
	localStorage.removeItem(cacheStorageKeys.danbooruTags);
	localStorage.removeItem(cacheStorageKeys.danbooruMeta);
	clearDanbooruPersistentCache();
	clearDanbooruCache();
}

export const bundledCacheVersion = bundledCacheSchemaVersion;
export const localDanbooruMergedCsvUrl = LOCAL_DANBOORU_MERGED_CSV_URL;
