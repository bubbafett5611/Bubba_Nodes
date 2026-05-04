const { app } = window.comfyAPI.app;
import { readBooleanSetting, readNumberSetting, readStringArray, writeStringArray } from "./storage.js";

const EXTENSION_NAME = "bubba.CheckpointTreeMenu";
const TARGET_NODE_CLASSES = new Set(["BubbaCheckpointLoader", "BubbaComboLoader"]);
const MENU_EXTRA_WIDTH_PX = 20;
const PREVIEW_PANEL_WIDTH_PX = 280;
const PREVIEW_IMAGE_EXTENSIONS = ["jpeg", "jpg", "png", "webp"];
const PREVIEW_ROUTE = "/bubba/checkpoint_preview";
const CIVITAI_LINK_ROUTE = "/bubba/checkpoint_civitai_link";
const CHECKPOINT_PREVIEW_ENABLED_KEY = "bubba.CheckpointPreview.Enabled";
const CHECKPOINT_MENU_DENSE_KEY = "bubba.CheckpointMenu.Dense";
const CHECKPOINT_MENU_FONT_SCALE_KEY = "bubba.CheckpointMenu.FontScale";
const CHECKPOINT_MENU_CONTRAST_KEY = "bubba.CheckpointMenu.Contrast";
const CHECKPOINT_MENU_ICON_SCALE_KEY = "bubba.CheckpointMenu.IconScale";
const CHECKPOINT_MENU_FAVORITES_KEY = "bubba.CheckpointMenu.Favorites";
const CHECKPOINT_MENU_RECENTS_KEY = "bubba.CheckpointMenu.Recents";
const CHECKPOINT_MENU_RECENTS_LIMIT_KEY = "bubba.CheckpointMenu.RecentsLimit";
const CHECKPOINT_MENU_RECENTS_LIMIT_DEFAULT = 14;

let stylesInstalled = false;
let observerInstalled = false;
let previewPanel = null;
let previewImage = null;
let previewLabel = null;
let previewRequestToken = 0;
const civitaiLinkCache = new Map();
let activeMenuContext = null;

function installStyles() {
	if (stylesInstalled) {
		return;
	}
	stylesInstalled = true;

	const style = document.createElement("style");
	style.textContent = `
		.bubba-ckpt-menu {
			--bubba-accent: #4fb3ff;
			--bubba-border: rgba(255, 255, 255, 0.15);
			--bubba-elevated: rgba(255, 255, 255, 0.08);
			--bubba-font-scale: 1;
			--bubba-icon-scale: 1;
			--bubba-contrast: 1;
			background: linear-gradient(160deg, rgba(36, 43, 55, 0.96), rgba(18, 21, 30, 0.96));
			border: 1px solid var(--bubba-border);
			border-radius: 12px;
			backdrop-filter: blur(10px);
			box-shadow: 0 14px 40px rgba(0, 0, 0, 0.45);
			padding: 4px 0;
			max-height: min(70vh, 760px);
			overflow-y: auto;
			overflow-x: hidden;
			filter: contrast(var(--bubba-contrast));
		}
		.bubba-ckpt-menu.bubba-ckpt-menu-dense .litemenu-entry {
			margin: 0 4px;
		}
		.bubba-ckpt-menu .comfy-context-menu-filter {
			margin: 6px 8px;
			border-radius: 8px;
			border: 1px solid var(--bubba-border);
			background: rgba(10, 12, 18, 0.75);
		}
		.bubba-ckpt-menu .litemenu-entry {
			margin: 1px 6px;
			border-radius: 8px;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
			font-size: calc(13px * var(--bubba-font-scale));
			transition: background-color 120ms ease, transform 120ms ease;
		}
		.bubba-ckpt-menu .litemenu-entry:hover {
			background: rgba(79, 179, 255, 0.16);
			transform: translateX(1px);
		}
		.bubba-ckpt-folder {
			display: flex;
			align-items: center;
			gap: 6px;
			font-weight: 600;
			opacity: 0.96;
			background: rgba(255, 255, 255, 0.03);
		}
		.bubba-ckpt-folder-arrow {
			display: inline-flex;
			width: calc(16px * var(--bubba-icon-scale));
			justify-content: center;
			color: var(--bubba-accent);
			font-size: calc(10px * var(--bubba-icon-scale));
		}
		.bubba-ckpt-folder-label {
			flex: 1;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.bubba-ckpt-folder-count {
			font-size: 11px;
			opacity: 0.85;
			padding: 1px 6px;
			border-radius: 999px;
			border: 1px solid var(--bubba-border);
			background: var(--bubba-elevated);
		}
		.bubba-ckpt-file {
			opacity: 0.94;
		}
		.bubba-ckpt-file-entry {
			display: flex;
			align-items: center;
			gap: 8px;
		}
		.bubba-ckpt-quick-header {
			opacity: 0.85;
			font-size: calc(11px * var(--bubba-font-scale));
			font-weight: 700;
			letter-spacing: 0.03em;
			text-transform: uppercase;
			margin-top: 6px;
			padding: 3px 10px;
			pointer-events: none;
		}
		.bubba-ckpt-quick-item {
			background: rgba(255, 255, 255, 0.02);
		}
		.bubba-ckpt-file-label {
			flex: 1;
			min-width: 0;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
			padding-right: 8px;
			border-right: 1px solid rgba(255, 255, 255, 0.14);
		}
		.bubba-ckpt-info-btn {
			width: calc(18px * var(--bubba-icon-scale));
			height: calc(18px * var(--bubba-icon-scale));
			flex: 0 0 auto;
			border-radius: 50%;
			border: 1px solid rgba(95, 187, 255, 0.6);
			background: rgba(7, 14, 24, 0.94);
			color: #a8dcff;
			font-size: calc(11px * var(--bubba-icon-scale));
			line-height: calc(16px * var(--bubba-icon-scale));
			text-align: center;
			cursor: pointer;
			padding: 0;
			font-weight: 700;
			box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.32);
		}
		.bubba-ckpt-info-btn:hover {
			background: rgba(18, 38, 60, 0.98);
			border-color: rgba(138, 213, 255, 0.95);
			color: #d8f1ff;
		}
		.bubba-ckpt-menu .litemenu-entry.selected .bubba-ckpt-info-btn,
		.bubba-ckpt-menu .litemenu-entry[aria-selected="true"] .bubba-ckpt-info-btn,
		.bubba-ckpt-menu .litemenu-entry[data-selected="true"] .bubba-ckpt-info-btn {
			background: rgba(6, 11, 20, 0.96);
			border-color: rgba(156, 221, 255, 0.98);
			color: #e9f7ff;
			box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.35);
		}
		.bubba-ckpt-info-btn.is-loading {
			opacity: 0.7;
		}
		.bubba-ckpt-info-btn.is-missing {
			opacity: 0.4;
		}
		.bubba-ckpt-fav-btn {
			width: calc(18px * var(--bubba-icon-scale));
			height: calc(18px * var(--bubba-icon-scale));
			flex: 0 0 auto;
			border-radius: 50%;
			border: 1px solid rgba(255, 210, 105, 0.58);
			background: rgba(24, 18, 8, 0.92);
			color: #ffd56b;
			font-size: calc(11px * var(--bubba-icon-scale));
			line-height: calc(16px * var(--bubba-icon-scale));
			text-align: center;
			cursor: pointer;
			padding: 0;
			font-weight: 700;
		}
		.bubba-ckpt-fav-btn:hover {
			background: rgba(62, 45, 14, 0.98);
			border-color: rgba(255, 224, 138, 0.95);
			color: #ffe8a8;
		}
		.bubba-ckpt-fav-btn.is-on {
			background: rgba(74, 55, 16, 0.98);
			border-color: rgba(255, 225, 130, 0.98);
			color: #fff1c2;
		}
		.bubba-ckpt-kb-focus {
			outline: 1px solid rgba(153, 220, 255, 0.9);
			outline-offset: -1px;
		}
		.bubba-ckpt-prefix {
			display: none;
			opacity: 0.65;
		}
		.bubba-ckpt-menu:has(input:not(:placeholder-shown)) .bubba-ckpt-folder-contents {
			display: block !important;
		}
		.bubba-ckpt-menu:has(input:not(:placeholder-shown)) .bubba-ckpt-folder {
			display: none;
		}
		.bubba-ckpt-menu:has(input:not(:placeholder-shown)) .bubba-ckpt-prefix {
			display: inline;
		}
		.bubba-ckpt-menu:has(input:not(:placeholder-shown)) .litemenu-entry {
			padding-left: 2px !important;
		}
		.bubba-ckpt-preview {
			position: fixed;
			z-index: 11000;
			width: ${PREVIEW_PANEL_WIDTH_PX}px;
			max-width: min(42vw, ${PREVIEW_PANEL_WIDTH_PX}px);
			pointer-events: none;
			opacity: 0;
			transform: translateY(2px);
			transition: opacity 90ms ease, transform 90ms ease;
			padding: 8px;
			border-radius: 12px;
			border: 1px solid var(--bubba-border);
			background: linear-gradient(160deg, rgba(26, 31, 40, 0.97), rgba(13, 16, 22, 0.97));
			box-shadow: 0 16px 38px rgba(0, 0, 0, 0.5);
		}
		.bubba-ckpt-preview.is-visible {
			opacity: 1;
			transform: translateY(0);
		}
		.bubba-ckpt-preview img {
			display: block;
			width: 100%;
			height: auto;
			max-height: min(50vh, 420px);
			object-fit: contain;
			border-radius: 8px;
			background: rgba(255, 255, 255, 0.03);
		}
		.bubba-ckpt-preview-label {
			margin-top: 6px;
			font-size: 12px;
			opacity: 0.9;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
	`;
	document.body.appendChild(style);
}

function _readBooleanSetting(key, fallback) {
	return readBooleanSetting(key, fallback);
}

function _readNumberSetting(key, fallback, min, max) {
	return readNumberSetting(key, fallback, min, max);
}

function _readStringArray(key) {
	return readStringArray(key);
}

function _writeStringArray(key, values) {
	writeStringArray(key, values);
}

function _normalizedPath(value) {
	return String(value || "").replace(/\\/g, "/").trim();
}

function getFavoritePaths() {
	return _readStringArray(CHECKPOINT_MENU_FAVORITES_KEY);
}

function isFavoritePath(path) {
	const target = _normalizedPath(path);
	if (!target) {
		return false;
	}
	return getFavoritePaths().includes(target);
}

function toggleFavoritePath(path) {
	const target = _normalizedPath(path);
	if (!target) {
		return false;
	}
	const current = getFavoritePaths();
	const index = current.indexOf(target);
	if (index >= 0) {
		current.splice(index, 1);
		_writeStringArray(CHECKPOINT_MENU_FAVORITES_KEY, current);
		return false;
	}
	current.unshift(target);
	_writeStringArray(CHECKPOINT_MENU_FAVORITES_KEY, current);
	return true;
}

function getRecentPaths() {
	return _readStringArray(CHECKPOINT_MENU_RECENTS_KEY);
}

function pushRecentPath(path) {
	const target = _normalizedPath(path);
	if (!target) {
		return;
	}
	const next = getRecentPaths().filter((item) => item !== target);
	next.unshift(target);
	const limit = _readNumberSetting(CHECKPOINT_MENU_RECENTS_LIMIT_KEY, CHECKPOINT_MENU_RECENTS_LIMIT_DEFAULT, 0, 50);
	_writeStringArray(CHECKPOINT_MENU_RECENTS_KEY, next.slice(0, limit));
}

function applyMenuPreferences(menu) {
	if (!menu) {
		return;
	}
	const dense = _readBooleanSetting(CHECKPOINT_MENU_DENSE_KEY, false);
	const fontScale = _readNumberSetting(CHECKPOINT_MENU_FONT_SCALE_KEY, 1, 0.8, 1.4);
	const contrast = _readNumberSetting(CHECKPOINT_MENU_CONTRAST_KEY, 1, 0.8, 1.5);
	const iconScale = _readNumberSetting(CHECKPOINT_MENU_ICON_SCALE_KEY, 1, 0.8, 1.6);

	menu.classList.toggle("bubba-ckpt-menu-dense", dense);
	menu.style.setProperty("--bubba-font-scale", String(fontScale));
	menu.style.setProperty("--bubba-contrast", String(contrast));
	menu.style.setProperty("--bubba-icon-scale", String(iconScale));
}

function ensurePreviewPanel() {
	if (previewPanel && previewImage && previewLabel) {
		return;
	}

	previewPanel = document.createElement("div");
	previewPanel.className = "bubba-ckpt-preview";

	previewImage = document.createElement("img");
	previewImage.alt = "Checkpoint preview";

	previewLabel = document.createElement("div");
	previewLabel.className = "bubba-ckpt-preview-label";

	previewPanel.appendChild(previewImage);
	previewPanel.appendChild(previewLabel);
	document.body.appendChild(previewPanel);
}

function hidePreviewPanel() {
	previewRequestToken += 1;
	if (previewPanel) {
		previewPanel.classList.remove("is-visible");
	}
}

function isCheckpointPreviewEnabled() {
	const raw = localStorage.getItem(CHECKPOINT_PREVIEW_ENABLED_KEY);
	return raw === null ? true : raw !== "false";
}

function positionPreviewPanel(anchorElement) {
	if (!previewPanel || !anchorElement) {
		return;
	}

	const anchor = anchorElement.getBoundingClientRect();
	const panelRect = previewPanel.getBoundingClientRect();
	const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
	const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
	const gap = 12;

	let left = anchor.right + gap;
	if (left + panelRect.width > viewportWidth - 10) {
		left = anchor.left - panelRect.width - gap;
	}
	left = Math.max(10, Math.min(left, viewportWidth - panelRect.width - 10));

	let top = anchor.top - 8;
	top = Math.max(10, Math.min(top, viewportHeight - panelRect.height - 10));

	previewPanel.style.left = `${Math.round(left)}px`;
	previewPanel.style.top = `${Math.round(top)}px`;
}

function buildPreviewCandidates(rawCheckpointPath) {
	const normalized = String(rawCheckpointPath || "").trim().replace(/\\/g, "/");
	if (!normalized) {
		return [];
	}

	const lastDot = normalized.lastIndexOf(".");
	const base = lastDot > 0 ? normalized.slice(0, lastDot) : normalized;
	const candidates = [];

	for (const ext of PREVIEW_IMAGE_EXTENSIONS) {
		candidates.push(`${base}.preview.${ext}`);
	}
	for (const ext of PREVIEW_IMAGE_EXTENSIONS) {
		candidates.push(`${base}.${ext}`);
	}

	return candidates;
}

function createCheckpointPreviewUrls(filename) {
	const normalized = String(filename || "").replace(/\\/g, "/");
	const slashIdx = normalized.lastIndexOf("/");
	const baseName = slashIdx >= 0 ? normalized.slice(slashIdx + 1) : normalized;
	const subfolder = slashIdx >= 0 ? normalized.slice(0, slashIdx) : "";

	const urls = [];
	const pushUrl = (paramsObj) => {
		const params = new URLSearchParams(paramsObj);
		urls.push(`/view?${params.toString()}`);
	};

	// Support both full relative path and split filename/subfolder forms.
	pushUrl({ filename: normalized, type: "checkpoints" });
	if (subfolder) {
		pushUrl({ filename: baseName, subfolder, type: "checkpoints" });
	}

	// Some builds may map previews through generic types; keep as fallback.
	pushUrl({ filename: normalized, type: "output" });
	if (subfolder) {
		pushUrl({ filename: baseName, subfolder, type: "output" });
	}

	return Array.from(new Set(urls));
}

function createBubbaPreviewUrl(checkpointPath) {
	const params = new URLSearchParams({ model: String(checkpointPath || "") });
	return `${PREVIEW_ROUTE}?${params.toString()}`;
}

function createCivitaiLookupUrl(checkpointPath) {
	const params = new URLSearchParams({ model: String(checkpointPath || "") });
	return `${CIVITAI_LINK_ROUTE}?${params.toString()}`;
}

async function getCivitaiUrl(checkpointPath) {
	const key = String(checkpointPath || "").trim();
	if (!key) {
		return null;
	}

	if (civitaiLinkCache.has(key)) {
		return civitaiLinkCache.get(key);
	}

	try {
		const response = await fetch(createCivitaiLookupUrl(key));
		if (!response.ok) {
			civitaiLinkCache.set(key, null);
			return null;
		}
		const payload = await response.json();
		const url = typeof payload?.url === "string" ? payload.url : null;
		civitaiLinkCache.set(key, url);
		return url;
	} catch {
		civitaiLinkCache.set(key, null);
		return null;
	}
}

function resolveFirstExistingPreview(checkpointPath, candidates) {
	return new Promise((resolve) => {
		const flattened = [createBubbaPreviewUrl(checkpointPath)];
		for (const candidate of candidates) {
			flattened.push(...createCheckpointPreviewUrls(candidate));
		}

		const tryAt = (index) => {
			if (index >= flattened.length) {
				resolve(null);
				return;
			}

			const testUrl = flattened[index];
			const probe = new Image();
			probe.onload = () => resolve({ url: testUrl });
			probe.onerror = () => tryAt(index + 1);
			probe.src = testUrl;
		};
		tryAt(0);
	});
}

async function showPreviewForEntry(entryElement) {
	if (!isCheckpointPreviewEnabled()) {
		hidePreviewPanel();
		return;
	}

	ensurePreviewPanel();
	if (!previewPanel || !previewImage || !previewLabel) {
		return;
	}

	const checkpointPath = entryElement?.dataset?.bubbaCkptPath;
	const candidates = buildPreviewCandidates(checkpointPath);
	if (!candidates.length) {
		hidePreviewPanel();
		return;
	}

	const requestToken = ++previewRequestToken;
	const preview = await resolveFirstExistingPreview(checkpointPath, candidates);
	if (requestToken !== previewRequestToken) {
		return;
	}
	if (!preview) {
		const fallbackLabel = candidates[0].split("/").pop() || candidates[0];
		previewImage.removeAttribute("src");
		previewLabel.textContent = `No preview found for ${fallbackLabel}`;
		previewPanel.classList.add("is-visible");
		positionPreviewPanel(entryElement);
		return;
	}

	previewImage.src = preview.url;
	const chosenName = candidates[0].split("/").pop() || candidates[0];
	previewLabel.textContent = chosenName;
	previewPanel.classList.add("is-visible");
	positionPreviewPanel(entryElement);
}

function bindEntryPreview(entryElement) {
	if (!entryElement || entryElement.dataset?.bubbaPreviewBound === "1") {
		return;
	}
	entryElement.dataset.bubbaPreviewBound = "1";

	entryElement.addEventListener("mouseenter", () => {
		showPreviewForEntry(entryElement);
	});

	entryElement.addEventListener("mouseleave", () => {
		hidePreviewPanel();
	});
}

function bindEntrySelectionTracking(entryElement) {
	if (!entryElement || entryElement.dataset?.bubbaSelectionTracked === "1") {
		return;
	}
	entryElement.dataset.bubbaSelectionTracked = "1";

	entryElement.addEventListener("click", () => {
		const checkpointPath = entryElement.dataset?.bubbaCkptPath;
		pushRecentPath(checkpointPath);
		hidePreviewPanel();
	});
}

function ensureFileEntryLayout(entryElement) {
	entryElement.classList.add("bubba-ckpt-file-entry");
	let label = entryElement.querySelector(":scope > .bubba-ckpt-file-label");
	if (label) {
		return label;
	}

	label = document.createElement("span");
	label.className = "bubba-ckpt-file-label";
	while (entryElement.firstChild) {
		label.appendChild(entryElement.firstChild);
	}
	entryElement.appendChild(label);
	return label;
}

function bindEntryCivitaiButton(entryElement) {
	if (!entryElement || entryElement.dataset?.bubbaCivitaiBound === "1") {
		return;
	}
	entryElement.dataset.bubbaCivitaiBound = "1";

	ensureFileEntryLayout(entryElement);

	const button = document.createElement("button");
	button.type = "button";
	button.className = "bubba-ckpt-info-btn";
	button.textContent = "i";
	button.title = "Open CivitAI page";
	entryElement.appendChild(button);

	button.addEventListener("mousedown", (event) => {
		event.preventDefault();
		event.stopPropagation();
	});

	button.addEventListener("click", async (event) => {
		event.preventDefault();
		event.stopPropagation();

		const checkpointPath = entryElement.dataset?.bubbaCkptPath;
		button.classList.add("is-loading");
		const url = await getCivitaiUrl(checkpointPath);
		button.classList.remove("is-loading");

		if (!url) {
			button.classList.add("is-missing");
			button.title = "No CivitAI link found for this model";
			return;
		}

		button.classList.remove("is-missing");
		button.title = "Open CivitAI page";
		window.open(url, "_blank", "noopener,noreferrer");
	});
}

function bindEntryFavoriteButton(entryElement) {
	if (!entryElement || entryElement.dataset?.bubbaFavoriteBound === "1") {
		return;
	}
	entryElement.dataset.bubbaFavoriteBound = "1";

	ensureFileEntryLayout(entryElement);

	const button = document.createElement("button");
	button.type = "button";
	button.className = "bubba-ckpt-fav-btn";
	button.title = "Toggle favorite";

	const syncState = () => {
		const on = isFavoritePath(entryElement.dataset?.bubbaCkptPath);
		button.classList.toggle("is-on", on);
		button.textContent = on ? "★" : "☆";
	};

	syncState();
	entryElement.appendChild(button);

	button.addEventListener("mousedown", (event) => {
		event.preventDefault();
		event.stopPropagation();
	});

	button.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		toggleFavoritePath(entryElement.dataset?.bubbaCkptPath);

		// Sync all star buttons in the current menu (quick-section copies included)
		const menu = activeMenuContext?.menu;
		if (menu?.isConnected) {
			for (const btn of menu.querySelectorAll(".bubba-ckpt-fav-btn")) {
				const entry = btn.closest("[data-bubba-ckpt-path], [data-value]");
				const path = entry?.dataset?.bubbaCkptPath || entry?.getAttribute("data-value");
				if (path) {
					const on = isFavoritePath(path);
					btn.classList.toggle("is-on", on);
					btn.textContent = on ? "★" : "☆";
				}
			}
		} else {
			syncState();
		}
	});
}

function buildQuickSection(title, paths, entryByPath, displayNameWithoutExtension) {
	if (!paths.length) {
		return null;
	}

	const section = document.createDocumentFragment();
	const header = document.createElement("div");
	header.className = "litemenu-entry bubba-ckpt-quick-header";
	header.textContent = title;
	section.appendChild(header);

	for (const path of paths) {
		const sourceEntry = entryByPath.get(path);
		if (!sourceEntry) {
			continue;
		}

		const quickItem = document.createElement("div");
		quickItem.className = "litemenu-entry bubba-ckpt-file bubba-ckpt-quick-item";
		quickItem.dataset.bubbaCkptPath = path;
		quickItem.setAttribute("data-value", path);
		const fileLeaf = path.split("/").pop() || path;
		quickItem.textContent = displayNameWithoutExtension(fileLeaf);

		bindEntryPreview(quickItem);
		bindEntrySelectionTracking(quickItem);
		bindEntryCivitaiButton(quickItem);
		bindEntryFavoriteButton(quickItem);

		quickItem.addEventListener("click", (event) => {
			if (event.defaultPrevented) {
				return;
			}
			sourceEntry.click();
		});

		section.appendChild(quickItem);
	}

	return section;
}

function setupKeyboardNavigation(menu) {
	if (!menu || menu.dataset?.bubbaKeyboardBound === "1") {
		return;
	}
	menu.dataset.bubbaKeyboardBound = "1";

	const selectableEntries = () => Array.from(menu.querySelectorAll(".litemenu-entry"))
		.filter((entry) => !entry.classList.contains("bubba-ckpt-quick-header"))
		.filter((entry) => entry.offsetParent !== null);

	let focusedEntry = null;
	const setFocusedEntry = (entry) => {
		if (focusedEntry && focusedEntry !== entry) {
			focusedEntry.classList.remove("bubba-ckpt-kb-focus");
		}
		focusedEntry = entry || null;
		if (focusedEntry) {
			focusedEntry.classList.add("bubba-ckpt-kb-focus");
			if (typeof focusedEntry.scrollIntoView === "function") {
				focusedEntry.scrollIntoView({ block: "nearest" });
			}
		}
	};

	const chooseInitialFocus = () => {
		const preferred = menu.querySelector(".litemenu-entry.bubba-ckpt-selected, .litemenu-entry.selected, .litemenu-entry[aria-selected='true'], .litemenu-entry[data-selected='true']");
		if (preferred) {
			setFocusedEntry(preferred);
			return;
		}
		const list = selectableEntries();
		if (list.length) {
			setFocusedEntry(list[0]);
		}
	};

	const keyHandler = (event) => {
		const list = selectableEntries();
		if (!list.length) {
			return;
		}

		if (!focusedEntry || !list.includes(focusedEntry)) {
			setFocusedEntry(list[0]);
		}

		const currentIndex = Math.max(0, list.indexOf(focusedEntry));
		if (event.key === "ArrowDown") {
			event.preventDefault();
			setFocusedEntry(list[(currentIndex + 1) % list.length]);
			return;
		}
		if (event.key === "ArrowUp") {
			event.preventDefault();
			setFocusedEntry(list[(currentIndex - 1 + list.length) % list.length]);
			return;
		}
		if (event.key === "Enter") {
			event.preventDefault();
			focusedEntry?.click();
			return;
		}
		if (event.key === "ArrowRight" && focusedEntry?.classList?.contains("bubba-ckpt-folder")) {
			event.preventDefault();
			const arrow = focusedEntry.querySelector(".bubba-ckpt-folder-arrow");
			if (arrow?.textContent === "▶") {
				focusedEntry.click();
			}
			return;
		}
		if (event.key === "ArrowLeft" && focusedEntry?.classList?.contains("bubba-ckpt-folder")) {
			event.preventDefault();
			const arrow = focusedEntry.querySelector(".bubba-ckpt-folder-arrow");
			if (arrow?.textContent === "▼") {
				focusedEntry.click();
			}
		}
	};

	menu.addEventListener("keydown", keyHandler, true);
	const filterInput = menu.querySelector(".comfy-context-menu-filter");
	if (filterInput) {
		filterInput.addEventListener("keydown", keyHandler, true);
	}

	chooseInitialFocus();
}

function isCheckpointWidget(node, widget) {
	return !!node && TARGET_NODE_CLASSES.has(node.comfyClass) && widget?.name === "ckpt_name";
}

function positionMenu(menu) {
	let left = app.canvas.last_mouse[0] - 10;
	let top = app.canvas.last_mouse[1] - 10;

	const bodyRect = document.body.getBoundingClientRect();
	const menuRect = menu.getBoundingClientRect();

	if (bodyRect.width && left > bodyRect.width - menuRect.width - 10) {
		left = bodyRect.width - menuRect.width - 10;
	}
	if (bodyRect.height && top > bodyRect.height - menuRect.height - 10) {
		top = bodyRect.height - menuRect.height - 10;
	}

	menu.style.left = `${left}px`;
	menu.style.top = `${top}px`;
}

function buildCheckpointTreeMenu(menu, selectedCheckpointValue = "", checkpointWidget = null) {
	menu.classList.add("bubba-ckpt-menu");
	applyMenuPreferences(menu);
	activeMenuContext = {
		menu,
		selectedCheckpointValue,
		checkpointWidget,
	};
	const selectedNormalized = String(selectedCheckpointValue || "").replace(/\\/g, "/").trim();

	const displayNameWithoutExtension = (name) => {
		const trimmed = String(name || "").trim();
		const dotIndex = trimmed.lastIndexOf(".");
		if (dotIndex <= 0) {
			return trimmed;
		}
		return trimmed.slice(0, dotIndex);
	};

	// Save original ComfyUI entries on first build; restore them on subsequent rebuilds
	// to prevent dynamically-added quick/folder elements from being re-processed.
	let entries;
	let rootContainer;
	if (menu._bubbaOriginalEntries) {
		entries = menu._bubbaOriginalEntries;
		rootContainer = menu._bubbaRootContainer;
		// Remove all previously added dynamic elements
		for (const el of menu.querySelectorAll(".bubba-ckpt-quick-header, .bubba-ckpt-quick-item, .bubba-ckpt-folder, .bubba-ckpt-folder-contents")) {
			el.remove();
		}
		// Re-attach original entries to rootContainer so the build loop can find them
		for (const entry of entries) {
			rootContainer.appendChild(entry);
		}
	} else {
		entries = Array.from(menu.querySelectorAll(".litemenu-entry"));
		if (!entries.length) {
			return;
		}
		rootContainer = entries[0].parentElement || menu;
		menu._bubbaOriginalEntries = entries;
		menu._bubbaRootContainer = rootContainer;
	}
	const splitBy = (navigator.platform || navigator.userAgent).includes("Win") ? /\/|\\/ : /\//;
	const itemsSymbol = Symbol("items");
	const folderMap = new Map();
	const rootItems = [];
	const entryByPath = new Map();

	for (const entry of entries) {
		const rawValue = entry.getAttribute("data-value") || "";
		const normalizedRawValue = rawValue.replace(/\\/g, "/");
		const pathParts = rawValue.split(splitBy).filter(Boolean);
		if (!pathParts.length) {
			rootItems.push(entry);
			continue;
		}

		entry.dataset.bubbaCkptPath = normalizedRawValue;
		entryByPath.set(normalizedRawValue, entry);
		entry.classList.remove("bubba-ckpt-selected");
		if (selectedNormalized && normalizedRawValue === selectedNormalized) {
			entry.classList.add("bubba-ckpt-selected");
		}

		// Only set text content on the first build; on rebuilds the entry already has
		// its label span + buttons in place — overwriting textContent would destroy them.
		if (!entry.dataset.bubbaContentSet) {
			entry.textContent = displayNameWithoutExtension(pathParts[pathParts.length - 1]);
			if (pathParts.length > 1) {
				const prefix = document.createElement("span");
				prefix.className = "bubba-ckpt-prefix";
				prefix.textContent = `${pathParts.slice(0, -1).join("/")}/`;
				entry.prepend(prefix);
			}
			entry.dataset.bubbaContentSet = "1";
		}

		if (pathParts.length === 1) {
			rootItems.push(entry);
			continue;
		}

		entry.remove();

		let currentLevel = folderMap;
		for (let idx = 0; idx < pathParts.length - 1; idx += 1) {
			const folderName = pathParts[idx];
			if (!currentLevel.has(folderName)) {
				currentLevel.set(folderName, new Map());
			}
			currentLevel = currentLevel.get(folderName);
		}

		if (!currentLevel.has(itemsSymbol)) {
			currentLevel.set(itemsSymbol, []);
		}
		currentLevel.get(itemsSymbol).push(entry);
	}

	for (const item of rootItems) {
		item.classList.add("bubba-ckpt-file");
		bindEntryPreview(item);
		bindEntrySelectionTracking(item);
		bindEntryCivitaiButton(item);
		bindEntryFavoriteButton(item);
		rootContainer.appendChild(item);
	}

	const favoritePaths = getFavoritePaths().filter((path) => entryByPath.has(path));
	const recentPaths = getRecentPaths().filter((path) => entryByPath.has(path) && !favoritePaths.includes(path));

	const countLeafItems = (map) => {
		let count = 0;
		const directItems = map.get(itemsSymbol) || [];
		count += directItems.length;
		for (const [name, childMap] of map.entries()) {
			if (name === itemsSymbol) {
				continue;
			}
			count += countLeafItems(childMap);
		}
		return count;
	};

	const hasSelectedItemInMap = (map) => {
		const directItems = map.get(itemsSymbol) || [];
		if (directItems.some((item) => item.classList?.contains("bubba-ckpt-selected") || item.classList?.contains("selected") || item.getAttribute?.("aria-selected") === "true" || item.getAttribute?.("data-selected") === "true")) {
			return true;
		}

		for (const [name, childMap] of map.entries()) {
			if (name === itemsSymbol) {
				continue;
			}
			if (hasSelectedItemInMap(childMap)) {
				return true;
			}
		}

		return false;
	};

	const createFolderElement = (folderName, itemCount) => {
		const element = document.createElement("div");
		element.className = "litemenu-entry bubba-ckpt-folder";

		const arrow = document.createElement("span");
		arrow.className = "bubba-ckpt-folder-arrow";
		arrow.textContent = "▶";

		const label = document.createElement("span");
		label.className = "bubba-ckpt-folder-label";
		label.textContent = folderName;

		const badge = document.createElement("span");
		badge.className = "bubba-ckpt-folder-count";
		badge.textContent = String(itemCount);

		element.appendChild(arrow);
		element.appendChild(label);
		element.appendChild(badge);
		element.style.paddingLeft = "5px";
		return element;
	};

	const insertFolderStructure = (parentElement, map, level = 0) => {
		for (const [folderName, contents] of map.entries()) {
			if (folderName === itemsSymbol) {
				continue;
			}

			const folderElement = createFolderElement(folderName, countLeafItems(contents));
			folderElement.style.paddingLeft = `${level * 10 + 5}px`;
			parentElement.appendChild(folderElement);

			const childContainer = document.createElement("div");
			childContainer.className = "bubba-ckpt-folder-contents";
			childContainer.style.display = "none";

			const items = contents.get(itemsSymbol) || [];
			for (const item of items) {
				item.classList.add("bubba-ckpt-file");
				bindEntryPreview(item);
				bindEntrySelectionTracking(item);
				bindEntryCivitaiButton(item);
				bindEntryFavoriteButton(item);
				item.style.paddingLeft = `${(level + 1) * 10 + 14}px`;
				childContainer.appendChild(item);
			}

			insertFolderStructure(childContainer, contents, level + 1);
			parentElement.appendChild(childContainer);

			if (hasSelectedItemInMap(contents)) {
				childContainer.style.display = "block";
				const arrow = folderElement.querySelector(".bubba-ckpt-folder-arrow");
				if (arrow) {
					arrow.textContent = "▼";
				}
			}

			folderElement.addEventListener("click", (event) => {
				event.stopPropagation();
				const arrow = folderElement.querySelector(".bubba-ckpt-folder-arrow");
				const visible = childContainer.style.display !== "none";
				childContainer.style.display = visible ? "none" : "block";
				arrow.textContent = visible ? "▶" : "▼";
			});
		}
	};

	insertFolderStructure(rootContainer, folderMap);

	const recentsDisplayLimit = _readNumberSetting(CHECKPOINT_MENU_RECENTS_LIMIT_KEY, CHECKPOINT_MENU_RECENTS_LIMIT_DEFAULT, 0, 50);
	const recentSection = buildQuickSection("Recent", recentPaths.slice(0, recentsDisplayLimit), entryByPath, displayNameWithoutExtension);
	const favoriteSection = buildQuickSection("Favorites", favoritePaths, entryByPath, displayNameWithoutExtension);
	if (recentSection) {
		rootContainer.prepend(recentSection);
	}
	if (favoriteSection) {
		rootContainer.prepend(favoriteSection);
	}

	const bodyRect = document.body.getBoundingClientRect();
	const viewportWidth = Math.max(0, Math.floor((bodyRect.width || window.innerWidth || 0) - 20));
	const desiredWidth = Math.ceil(menu.scrollWidth + MENU_EXTRA_WIDTH_PX);
	const nextWidth = Math.max(0, Math.min(desiredWidth, viewportWidth));
	menu.style.width = `${nextWidth}px`;
	positionMenu(menu);

	const selectedEntry = menu.querySelector(
		".litemenu-entry.bubba-ckpt-selected, .litemenu-entry.selected, .litemenu-entry[aria-selected='true'], .litemenu-entry[data-selected='true']"
	);
	if (selectedEntry && typeof selectedEntry.scrollIntoView === "function") {
		selectedEntry.scrollIntoView({ block: "nearest" });
	}

	setupKeyboardNavigation(menu);
}

function installMenuObserver() {
	if (observerInstalled) {
		return;
	}
	observerInstalled = true;

	const observer = new MutationObserver((mutations) => {
		const node = app.canvas.current_node;
		if (!node || !TARGET_NODE_CLASSES.has(node.comfyClass)) {
			return;
		}

		for (const mutation of mutations) {
			for (const removed of mutation.removedNodes) {
				if (removed.classList?.contains("litecontextmenu")) {
					hidePreviewPanel();
				}
			}
			for (const added of mutation.addedNodes) {
				if (!added.classList?.contains("litecontextmenu")) {
					continue;
				}

				const widget = app.canvas.getWidgetAtCursor();
				if (!isCheckpointWidget(node, widget)) {
					continue;
				}

				requestAnimationFrame(() => {
					if (!added.querySelector(".comfy-context-menu-filter")) {
						return;
					}
					buildCheckpointTreeMenu(added, String(widget?.value ?? ""), widget);
				});
				return;
			}
		}
	});

	observer.observe(document.body, { childList: true, subtree: false });
}

function installCheckpointTieredMenus() {
	installStyles();
	installMenuObserver();

	app.registerExtension({
		name: EXTENSION_NAME,
		beforeRegisterNodeDef(nodeType, nodeData) {
			if (!TARGET_NODE_CLASSES.has(nodeData?.name)) {
				return;
			}

			const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function onNodeCreatedWithTreeMenu() {
				return typeof originalOnNodeCreated === "function"
					? originalOnNodeCreated.apply(this, arguments)
					: undefined;
			};
		},
	});
}

export {
	installCheckpointTieredMenus,
};
