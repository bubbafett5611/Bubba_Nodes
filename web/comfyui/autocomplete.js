import { ComfyWidgets } from "../../../scripts/widgets.js";
import { $el } from "../../../scripts/ui.js";

const id = "bubba.Autocomplete";
const customWordsStorageKey = `${id}.CustomWords`;
const danbooruTagsStorageKey = `${id}.DanbooruTags`;
const danbooruMetaStorageKey = `${id}.DanbooruMeta`;
const danbooruEnabledStorageKey = `${id}.UseDanbooru`;
const danbooruMinCountStorageKey = `${id}.DanbooruMinCount`;
const debugStorageKey = `${id}.Debug`;
const bundledCacheSchemaVersion = 1;

const DANBOORU_BASE_URL = "https://danbooru.donmai.us/tags.json";
const DANBOORU_MAX_PAGES = 20;
const DANBOORU_MAX_FULL_SYNC_PAGES = 1000;
const DANBOORU_PAGE_SIZE = 200;
const DANBOORU_REQUEST_DELAY_MS = 200;
const BUNDLED_DANBOORU_CACHE_URL = new URL("./danbooru_cache.csv", import.meta.url);

let danbooruTagsMemoryCache = [];

const GROUP_WORDS = {
	common: [
		"masterpiece",
		"best quality",
		"high detail",
		"cinematic lighting",
		"volumetric lighting",
		"sharp focus",
		"depth of field",
	],
	appearance: ["silver hair", "long hair", "amber eyes", "freckles", "cat ears", "wolf ears", "tail"],
	body: ["slim", "athletic", "curvy", "petite", "tall", "soft body", "defined muscles"],
	clothing: ["hoodie", "jacket", "leather outfit", "armor", "dress", "stockings", "gloves"],
	pose: ["standing", "sitting", "dynamic pose", "looking at viewer", "from above", "cowboy shot"],
	expression: ["smile", "serious", "smirk", "blush", "confident", "playful", "determined"],
	scene: ["forest", "city street", "night", "sunset", "studio lighting", "rain", "indoors"],
	style: ["anime", "semi-realistic", "illustration", "digital painting", "lineart", "vibrant colors"],
	quality: ["8k", "ultra detailed", "detailed background", "clean lineart", "highres"],
	positive: ["masterpiece", "best quality", "high detail", "detailed face", "dynamic lighting"],
	negative: ["lowres", "blurry", "bad anatomy", "extra fingers", "deformed", "watermark", "text"],
};

$el("style", {
	textContent: `
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
	`,
	parent: document.body,
});

function toInt(value, fallback) {
	const parsed = Number.parseInt(String(value), 10);
	if (Number.isNaN(parsed)) {
		return fallback;
	}
	return parsed;
}

function clamp(value, min, max) {
	return Math.max(min, Math.min(max, value));
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

function isDebugEnabled() {
	return localStorage.getItem(debugStorageKey) === "true";
}

function logDebug(message) {
	if (!isDebugEnabled()) {
		return;
	}
	console.info(message);
}

function delay(ms) {
	return new Promise((resolve) => {
		setTimeout(resolve, ms);
	});
}

function normalizeEntry(entry, source) {
	if (!entry) {
		return null;
	}

	if (typeof entry === "string") {
		const text = entry.trim();
		if (!text) {
			return null;
		}
		return {
			text,
			source,
			count: null,
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
	return {
		text,
		source,
		count: Number.isFinite(count) ? count : null,
		category,
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
			map.set(key, entry);
		}
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

function getCustomWords() {
	return parseCustomWords(localStorage.getItem(customWordsStorageKey) || "");
}

function getDanbooruTags() {
	const parsed = parseJsonStorage(danbooruTagsStorageKey, []);
	if (Array.isArray(parsed) && parsed.length > 0) {
		const normalized = dedupeEntries(
			parsed
				.map((entry) => normalizeEntry(entry, "danbooru"))
				.filter(Boolean),
		);
		danbooruTagsMemoryCache = normalized;
		return normalized;
	}
	if (Array.isArray(danbooruTagsMemoryCache) && danbooruTagsMemoryCache.length > 0) {
		return danbooruTagsMemoryCache;
	}
	return [];
}

function setDanbooruTags(tags) {
	const serialized = tags.map((tag) => ({
		text: tag.text,
		count: tag.count,
		category: tag.category,
	}));
	danbooruTagsMemoryCache = dedupeEntries(
		serialized
			.map((entry) => normalizeEntry(entry, "danbooru"))
			.filter(Boolean),
	);
	try {
		localStorage.setItem(danbooruTagsStorageKey, JSON.stringify(serialized));
	} catch (error) {
		console.warn("Bubba Autocomplete: localStorage quota exceeded for Danbooru tags, using in-memory cache only.", error);
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

function isDanbooruEnabled() {
	return localStorage.getItem(danbooruEnabledStorageKey) !== "false";
}

function getDanbooruMinCount() {
	return Math.max(0, toInt(localStorage.getItem(danbooruMinCountStorageKey) || "0", 0));
}

async function loadBundledDanbooruCache() {
	const response = await fetch(BUNDLED_DANBOORU_CACHE_URL, {
		cache: "no-store",
		headers: {
			"Accept": "text/csv, text/plain;q=0.9, */*;q=0.8",
		},
	});
	if (!response.ok) {
		throw new Error(`Unable to load bundled Danbooru cache (${response.status}).`);
	}
	const csvText = await response.text();
	const tags = [];
	const lines = csvText
		.split(/\r?\n/g)
		.map((line) => line.trim())
		.filter(Boolean);

	let generatedAt = null;
	let minCount = 0;
	let pages = 0;

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
			} else if (key === "min_post_count") {
				minCount = Math.max(0, toInt(value, 0));
			} else if (key === "pages_fetched") {
				pages = Math.max(0, toInt(value, 0));
			}
			continue;
		}

		const header = line.toLowerCase();
		if (
			header === "tag,count" ||
			header === "tag,count,category" ||
			header === "name,post_count" ||
			header === "name,post_count,category"
		) {
			continue;
		}
		const parts = line.split(",");
		if (parts.length < 2) {
			continue;
		}

		const tag = parts[0].trim();
		const count = Math.max(0, toInt(parts[1].trim(), 0));
		const category = parts.length >= 3 ? normalizeDanbooruCategory(parts[2].trim()) : null;
		const entry = normalizeEntry({ name: tag, count, category }, "danbooru");
		if (entry) {
			tags.push(entry);
		}
	}

	return {
		tags,
		meta: {
			seedSource: "bundled",
			schemaVersion: bundledCacheSchemaVersion,
			generatedAt,
			minCount,
			pages,
		},
	};
}

async function ensureDanbooruCacheSeeded() {
	const existing = getDanbooruTags();
	if (existing.length > 0) {
		return;
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
			pages: bundled.meta.pages,
			minCount: bundled.meta.minCount,
			seedSource: bundled.meta.seedSource,
			schemaVersion: bundled.meta.schemaVersion,
			bundledGeneratedAt: bundled.meta.generatedAt,
			fetchMode: "bundled",
		});
		localStorage.setItem(danbooruMinCountStorageKey, String(bundled.meta.minCount));
	} catch (error) {
		console.warn("Bubba Autocomplete: failed to load bundled Danbooru cache", error);
	}
}

async function fetchDanbooruTags(options) {
	const fullSync = !!options?.fullSync;
	const pages = options?.pages;
	const minCount = options?.minCount;
	const safePages = clamp(toInt(pages, 3), 1, DANBOORU_MAX_PAGES);
	const safeMinCount = Math.max(0, toInt(minCount, 0));
	const collected = new Map();
	let pagesFetched = 0;
	let truncated = false;
	const maxPages = fullSync ? DANBOORU_MAX_FULL_SYNC_PAGES : safePages;
	logDebug(`Bubba Autocomplete: Starting ${fullSync ? "full" : "paged"} fetch (maxPages=${maxPages}, minCount=${safeMinCount}).`);

	for (let page = 1; page <= maxPages; page += 1) {
		logDebug(`Bubba Autocomplete: Fetching Danbooru page ${page}/${maxPages}...`);
		const params = new URLSearchParams();
		params.set("limit", String(DANBOORU_PAGE_SIZE));
		params.set("page", String(page));
		params.set("search[order]", "count");
		params.set("search[hide_empty]", "true");

		const url = `${DANBOORU_BASE_URL}?${params.toString()}`;
		const response = await fetch(url, {
			headers: {
				"Accept": "application/json",
			},
			cache: "no-store",
		});

		if (!response.ok) {
			throw new Error(`Danbooru API failed: ${response.status} ${response.statusText}`);
		}

		const payload = await response.json();
		if (!Array.isArray(payload)) {
			throw new Error("Danbooru API returned an unexpected payload.");
		}
		pagesFetched += 1;

		if (payload.length === 0) {
			logDebug(`Bubba Autocomplete: Page ${page} returned 0 rows, stopping.`);
			break;
		}

		let lowestCountInPage = Number.POSITIVE_INFINITY;

		for (const row of payload) {
			const name = String(row?.name || "").trim();
			const count = toInt(row?.post_count ?? 0, 0);
			const category = normalizeDanbooruCategory(row?.category);
			lowestCountInPage = Math.min(lowestCountInPage, count);
			if (!name || count < safeMinCount) {
				continue;
			}
			const prev = collected.get(name);
			if (!prev || count > prev.count) {
				collected.set(name, { count, category });
			}
		}

		logDebug(`Bubba Autocomplete: Page ${page} processed (${payload.length} rows, ${collected.size} tags cached so far).`);

		if (payload.length < DANBOORU_PAGE_SIZE) {
			logDebug(`Bubba Autocomplete: Page ${page} below page size (${payload.length} < ${DANBOORU_PAGE_SIZE}), stopping.`);
			break;
		}

		if (fullSync && lowestCountInPage < safeMinCount) {
			logDebug(`Bubba Autocomplete: Page ${page} dropped below minCount (${lowestCountInPage} < ${safeMinCount}), stopping.`);
			break;
		}

		if (page < maxPages) {
			await delay(DANBOORU_REQUEST_DELAY_MS);
		}
	}

	if (fullSync && pagesFetched >= DANBOORU_MAX_FULL_SYNC_PAGES) {
		truncated = true;
		logDebug(`Bubba Autocomplete: Reached safety cap (${DANBOORU_MAX_FULL_SYNC_PAGES} pages), truncating.`);
	}

	const tags = [...collected.entries()]
		.map(([text, data]) => ({ text, count: data.count, category: data.category, source: "danbooru" }))
		.sort((a, b) => {
			if (b.count !== a.count) {
				return b.count - a.count;
			}
			return a.text.localeCompare(b.text);
		});

	return {
		tags,
		pagesFetched,
		truncated,
		minCount: safeMinCount,
		mode: fullSync ? "full" : "paged",
	};
}

function parseStatusFromMeta() {
	const meta = getDanbooruMeta();
	if (!meta || !meta.updatedAt) {
		return "No cached Danbooru tags.";
	}
	const date = new Date(meta.updatedAt);
	const dateText = Number.isNaN(date.getTime()) ? String(meta.updatedAt) : date.toLocaleString();
	const countText = typeof meta.count === "number" ? formatNumber(meta.count) : "0";
	const pageText = typeof meta.pages === "number" ? String(meta.pages) : "?";
	const minCountText = typeof meta.minCount === "number" ? String(meta.minCount) : "0";
	const modeText = meta.fetchMode ? `, mode ${meta.fetchMode}` : "";
	const sourceText = meta.seedSource ? `, source ${meta.seedSource}` : "";
	const truncText = meta.truncated ? ", truncated" : "";
	return `Cached ${countText} Danbooru tags (${pageText} pages, min count ${minCountText}${modeText}${sourceText}${truncText}) on ${dateText}.`;
}

function getWordList(group) {
	const words = [];
	for (const item of GROUP_WORDS.common) {
		words.push({ text: item, source: "builtin", count: null });
	}
	for (const item of GROUP_WORDS[group] || []) {
		words.push({ text: item, source: "builtin", count: null });
	}
	for (const item of getCustomWords()) {
		words.push(item);
	}
	if (isDanbooruEnabled()) {
		for (const item of getDanbooruTags()) {
			words.push(item);
		}
	}
	return dedupeEntries(words);
}

class BubbaTextAutoComplete {
	constructor(inputEl, group) {
		this.inputEl = inputEl;
		this.group = group || "common";
		this.menuEl = $el("div.bubba-autocomplete", { parent: document.body });
		this.menuEl.style.display = "none";
		this.items = [];
		this.selectedIndex = -1;

		this.onInput = this.onInput.bind(this);
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
			const row = $el("div.bubba-autocomplete-item", {
				onmousedown: (event) => {
					event.preventDefault();
					this.insert(item);
				},
				parent: this.menuEl,
			});
			$el("span", {
				textContent: item.text,
				parent: row,
			});
			if (typeof item.count === "number") {
				const categoryLabel = getDanbooruCategoryLabel(item.category);
				const metaText = categoryLabel ? `${formatNumber(item.count)} | ${categoryLabel}` : formatNumber(item.count);
				$el("span.bubba-autocomplete-item-meta", {
					textContent: metaText,
					parent: row,
				});
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

	onInput() {
		if (!BubbaTextAutoComplete.enabled) {
			this.hide();
			return;
		}
		const { query } = this.getQuery();
		if (!query) {
			this.hide();
			return;
		}

		const results = getWordList(this.group)
			.filter((item) => item.text.toLowerCase().includes(query))
			.sort((a, b) => {
				const aStarts = a.text.toLowerCase().startsWith(query) ? 1 : 0;
				const bStarts = b.text.toLowerCase().startsWith(query) ? 1 : 0;
				if (bStarts !== aStarts) {
					return bStarts - aStarts;
				}
				const aCount = typeof a.count === "number" ? a.count : -1;
				const bCount = typeof b.count === "number" ? b.count : -1;
				if (bCount !== aCount) {
					return bCount - aCount;
				}
				return a.text.localeCompare(b.text);
			})
			.slice(0, BubbaTextAutoComplete.suggestionLimit);

		this.show(results);
	}

	onFocus() {
		if (!BubbaTextAutoComplete.enabled) return;
		this.onInput();
	}

	onBlur() {
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

async function openCustomWordsEditor() {
	try {
		logDebug("Bubba Autocomplete: Open File requested.");
		const tags = getDanbooruTags();
		if (tags.length) {
			const meta = getDanbooruMeta() || {};
			logDebug(`Bubba Autocomplete: Syncing ${tags.length} cached tags to danbooru_cache.csv before opening.`);
			await writeDanbooruCacheToFile(tags, meta);
		}
		await fetch("/bubba/open_cache");
		logDebug("Bubba Autocomplete: Opened danbooru_cache.csv.");
	} catch (e) {
		console.error("Bubba Autocomplete: could not open cache file", e);
	}
}

function buildDanbooruCacheCsvLines(tags, meta = {}) {
	const generatedAt = new Date().toISOString();
	const minCount = typeof meta.minCount === "number" ? meta.minCount : getDanbooruMinCount();
	const pagesFetched = typeof meta.pages === "number" ? meta.pages : 0;

	const lines = [
		`# schema_version=${bundledCacheSchemaVersion}`,
		"# source=danbooru",
		`# generated_at=${generatedAt}`,
		`# min_post_count=${minCount}`,
		`# pages_fetched=${pagesFetched}`,
		`# tag_count=${tags.length}`,
		"tag,count,category",
	];

	for (const tag of tags) {
		const text = String(tag.text || "").replace(/\r?\n/g, " ").trim();
		if (!text) {
			continue;
		}
		const count = typeof tag.count === "number" ? tag.count : 0;
		const category = normalizeDanbooruCategory(tag.category);
		lines.push(`${text},${count},${category ?? ""}`);
	}

	return lines;
}

async function writeDanbooruCacheToFile(tags, meta = {}) {
	const csvText = `${buildDanbooruCacheCsvLines(tags, meta).join("\n")}\n`;
	logDebug(`Bubba Autocomplete: Writing ${tags.length} tags to danbooru_cache.csv.`);
	const response = await fetch("/bubba/write_cache", {
		method: "POST",
		headers: {
			"Content-Type": "text/csv;charset=utf-8",
		},
		body: csvText,
	});
	if (!response.ok) {
		throw new Error(`Failed to write cache file (${response.status}).`);
	}
	logDebug("Bubba Autocomplete: Cache file write complete.");
}

function downloadDanbooruCacheFile() {
	const tags = getDanbooruTags();
	if (!tags.length) {
		alert("Bubba Autocomplete: no Danbooru cache available to export.");
		return;
	}

	const meta = getDanbooruMeta() || {};
	const lines = buildDanbooruCacheCsvLines(tags, meta);

	const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = "danbooru_cache.csv";
	a.style.display = "none";
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

async function refreshDanbooruTagsFromPrompts(buttonEl, fullSync = false) {
	const currentMeta = getDanbooruMeta();
	const defaultPages = String(currentMeta?.pages ?? 10);
	const defaultMinCount = String(currentMeta?.minCount ?? getDanbooruMinCount());
	let pages = 1;

	if (!fullSync) {
		const pagesInput = window.prompt(`How many Danbooru pages to fetch? (1-${DANBOORU_MAX_PAGES}, ${DANBOORU_PAGE_SIZE} tags per page)`, defaultPages);
		if (pagesInput === null) {
			return;
		}
		pages = clamp(toInt(pagesInput, toInt(defaultPages, 10)), 1, DANBOORU_MAX_PAGES);
	}

	const minCountInput = window.prompt("Minimum post count for tags (0 for all):", defaultMinCount);
	if (minCountInput === null) {
		return;
	}
	const minCount = Math.max(0, toInt(minCountInput, toInt(defaultMinCount, 0)));

	if (fullSync) {
		const ok = window.confirm(`Full sync will fetch every Danbooru tag with post count >= ${minCount}. This can take a while. Continue?`);
		if (!ok) {
			return;
		}
	}

	if (buttonEl) {
		buttonEl.disabled = true;
		buttonEl.textContent = fullSync ? "Full Sync..." : "Fetching...";
	}

	try {
		const result = await fetchDanbooruTags({
			pages,
			minCount,
			fullSync,
		});
		logDebug(`Bubba Autocomplete: Fetch complete (${result.tags.length} tags from ${result.pagesFetched} pages).`);
		const nextMeta = {
			updatedAt: new Date().toISOString(),
			count: result.tags.length,
			pages: result.pagesFetched,
			minCount,
			fetchMode: result.mode,
			truncated: result.truncated,
			seedSource: "live",
			schemaVersion: bundledCacheSchemaVersion,
		};
		setDanbooruTags(result.tags);
		setDanbooruMeta(nextMeta);
		localStorage.setItem(danbooruMinCountStorageKey, String(minCount));
		await writeDanbooruCacheToFile(result.tags, nextMeta);
		logDebug("Bubba Autocomplete: Cache persisted to localStorage and danbooru_cache.csv.");
		const truncText = result.truncated ? " (reached safety page cap)" : "";
		alert(`Bubba Autocomplete: Cached ${formatNumber(result.tags.length)} Danbooru tags from ${result.pagesFetched} pages${truncText}.`);
	} catch (error) {
		console.error(error);
		alert(`Bubba Autocomplete: Failed to fetch Danbooru tags. ${error?.message || "Unknown error"}`);
	} finally {
		if (buttonEl) {
			buttonEl.disabled = false;
			buttonEl.textContent = fullSync ? "Full Sync (All >= Min Count)" : "Refresh from Danbooru";
		}
	}
}

function clearDanbooruTagCache() {
	localStorage.removeItem(danbooruTagsStorageKey);
	localStorage.removeItem(danbooruMetaStorageKey);
}

export {
	id,
	BubbaTextAutoComplete,
	installStringWidgetHook,
	ensureDanbooruCacheSeeded,
	isDanbooruEnabled,
	danbooruEnabledStorageKey,
	debugStorageKey,
	openCustomWordsEditor,
	downloadDanbooruCacheFile,
	refreshDanbooruTagsFromPrompts,
	clearDanbooruTagCache,
	parseStatusFromMeta,
};
