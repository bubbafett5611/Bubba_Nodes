const { app } = window.comfyAPI.app;
import {
	createQuickSection,
	installLiteMenuObserver,
	makeHeadingCollapsible as makeSharedHeadingCollapsible,
	setupKeyboardNavigation,
} from "./menu_shared.js";
import { readStringArray, writeStringArray } from "./storage.js";

const EXTENSION_NAME = "bubba.EmptyLatentSizeMenu";
const TARGET_NODE_CLASS = "BubbaEmptyLatentBySize";
const TARGET_WIDGET_NAME = "size";
const SIZE_MENU_FAVORITES_KEY = "bubba.SizeMenu.Favorites";
const SIZE_MENU_RECENTS_KEY = "bubba.SizeMenu.Recents";
const SIZE_MENU_RECENTS_LIMIT = 12;
const SIZE_MENU_EXPANDED_KEY = "bubba.SizeMenu.Expanded";

let stylesInstalled = false;
let previewPanel = null;
let previewRect = null;
let previewTitle = null;
let previewMeta = null;
let activeMenu = null;

function installStyles() {
    if (stylesInstalled) {
        return;
    }
    stylesInstalled = true;

    const style = document.createElement("style");
    style.textContent = `
        .bubba-size-menu {
            --bubba-size-border: rgba(255, 255, 255, 0.14);
            --bubba-size-bg: linear-gradient(160deg, rgba(34, 41, 53, 0.96), rgba(17, 21, 30, 0.96));
            background: var(--bubba-size-bg);
            border: 1px solid var(--bubba-size-border);
            border-radius: 12px;
            box-shadow: 0 14px 38px rgba(0, 0, 0, 0.45);
            padding: 4px 0;
            max-height: min(72vh, 760px);
            overflow-y: auto;
            overflow-x: hidden;
        }
        .bubba-size-menu .comfy-context-menu-filter {
            margin: 6px 8px;
            border-radius: 8px;
            border: 1px solid var(--bubba-size-border);
            background: rgba(10, 12, 17, 0.74);
        }
        .bubba-size-menu .litemenu-entry {
            margin: 1px 6px;
            border-radius: 8px;
            font-size: 13px;
            transition: background-color 120ms ease, transform 120ms ease;
        }
        .bubba-size-menu .litemenu-entry.bubba-size-focused {
            background: rgba(102, 184, 255, 0.18);
            box-shadow: inset 0 0 0 1px rgba(102, 184, 255, 0.34);
        }
        .bubba-size-menu .litemenu-entry.bubba-size-selected {
            background: rgba(102, 184, 255, 0.2);
            box-shadow: inset 0 0 0 1px rgba(102, 184, 255, 0.42);
        }
        .bubba-size-menu .litemenu-entry:hover:not(.bubba-size-heading):not(.bubba-size-quick-header) {
            background: rgba(102, 184, 255, 0.14);
            transform: translateX(1px);
        }
        .bubba-size-heading,
        .bubba-size-quick-header {
            opacity: 0.88;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-top: 6px;
            padding: 3px 10px;
            background: transparent !important;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .bubba-size-quick-header {
            pointer-events: none;
        }
        .bubba-size-heading {
            cursor: pointer;
            user-select: none;
        }
        .bubba-size-heading:hover {
            opacity: 1;
            color: rgba(102, 184, 255, 0.9);
        }
        .bubba-size-heading-text {
            flex: 1;
        }
        .bubba-size-chevron {
            font-size: 9px;
            opacity: 0.7;
            transition: transform 120ms ease;
            flex: 0 0 auto;
        }
        .bubba-size-heading.is-collapsed .bubba-size-chevron {
            transform: rotate(-90deg);
        }
        .bubba-size-option {
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
        }
        .bubba-size-option-main {
            display: flex;
            align-items: center;
            flex: 1;
            min-width: 0;
        }
        .bubba-size-option-label {
            font-weight: 600;
            letter-spacing: 0;
            flex: 0 0 auto;
        }
        .bubba-size-model-pill {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            opacity: 0.9;
            border: 1px solid rgba(130, 210, 255, 0.3);
            background: rgba(102, 184, 255, 0.12);
            border-radius: 999px;
            padding: 2px 6px;
            flex: 0 0 auto;
        }
        .bubba-size-mp-pill {
            font-size: 11px;
            opacity: 0.9;
            border: 1px solid var(--bubba-size-border);
            background: rgba(255, 255, 255, 0.08);
            border-radius: 999px;
            padding: 1px 6px;
            flex: 0 0 auto;
        }
        .bubba-size-fav-btn {
            width: 18px;
            height: 18px;
            flex: 0 0 auto;
            border-radius: 50%;
            border: 1px solid rgba(255, 210, 105, 0.58);
            background: rgba(24, 18, 8, 0.92);
            color: #ffd56b;
            font-size: 11px;
            line-height: 16px;
            text-align: center;
            cursor: pointer;
            padding: 0;
            font-weight: 700;
        }
        .bubba-size-fav-btn:hover {
            background: rgba(62, 45, 14, 0.98);
            border-color: rgba(255, 224, 138, 0.95);
            color: #ffe8a8;
        }
        .bubba-size-fav-btn.is-on {
            background: rgba(74, 55, 16, 0.98);
            border-color: rgba(255, 225, 130, 0.98);
            color: #fff1c2;
        }
        .bubba-size-preview {
            position: fixed;
            z-index: 11000;
            width: 240px;
            pointer-events: none;
            opacity: 0;
            transform: translateY(2px);
            transition: opacity 90ms ease, transform 90ms ease;
            padding: 10px;
            border-radius: 12px;
            border: 1px solid var(--bubba-size-border);
            background: linear-gradient(160deg, rgba(24, 30, 39, 0.97), rgba(11, 15, 22, 0.97));
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.5);
        }
        .bubba-size-preview.is-visible {
            opacity: 1;
            transform: translateY(0);
        }
        .bubba-size-preview-title {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 8px;
            opacity: 0.95;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .bubba-size-preview-stage {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 168px;
            height: 168px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
            margin-bottom: 8px;
        }
        .bubba-size-preview-rect {
            border-radius: 6px;
            border: 2px solid rgba(102, 184, 255, 0.95);
            background: linear-gradient(145deg, rgba(102, 184, 255, 0.24), rgba(102, 184, 255, 0.1));
            box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.2);
        }
        .bubba-size-preview-meta {
            font-size: 12px;
            opacity: 0.92;
        }
    `;
    document.body.appendChild(style);
}

function _readStringArray(key) {
    return readStringArray(key);
}

function _writeStringArray(key, values) {
    writeStringArray(key, values);
}

function getFavoriteValues() {
    return _readStringArray(SIZE_MENU_FAVORITES_KEY);
}

function isFavoriteValue(value) {
    return getFavoriteValues().includes(String(value || ""));
}

function toggleFavoriteValue(value) {
    const target = String(value || "");
    if (!target) {
        return false;
    }
    const current = getFavoriteValues();
    const index = current.indexOf(target);
    if (index >= 0) {
        current.splice(index, 1);
        _writeStringArray(SIZE_MENU_FAVORITES_KEY, current);
        return false;
    }
    current.unshift(target);
    _writeStringArray(SIZE_MENU_FAVORITES_KEY, current);
    return true;
}

function getRecentValues() {
    return _readStringArray(SIZE_MENU_RECENTS_KEY);
}

function pushRecentValue(value) {
    const target = String(value || "");
    if (!target) {
        return;
    }
    const next = getRecentValues().filter((item) => item !== target);
    next.unshift(target);
    _writeStringArray(SIZE_MENU_RECENTS_KEY, next.slice(0, SIZE_MENU_RECENTS_LIMIT));
}

function getExpandedGroups() {
    return new Set(_readStringArray(SIZE_MENU_EXPANDED_KEY));
}

function toggleCollapsedGroup(heading) {
    const current = _readStringArray(SIZE_MENU_EXPANDED_KEY);
    const index = current.indexOf(heading);
    if (index >= 0) {
        current.splice(index, 1);
        _writeStringArray(SIZE_MENU_EXPANDED_KEY, current);
        return true;
    }
    current.push(heading);
    _writeStringArray(SIZE_MENU_EXPANDED_KEY, current);
    return false;
}

function makeHeadingCollapsible(headingEntry, presetEntries, heading, isCollapsed) {
    makeSharedHeadingCollapsible({
        headingEntry,
        controlledEntries: presetEntries,
        isCollapsed,
        onToggle() {
            return toggleCollapsedGroup(heading);
        },
        chevronSelector: ".bubba-size-chevron",
    });
}

function ensurePreviewPanel() {
    if (previewPanel && previewRect && previewTitle && previewMeta) {
        return;
    }

    previewPanel = document.createElement("div");
    previewPanel.className = "bubba-size-preview";

    previewTitle = document.createElement("div");
    previewTitle.className = "bubba-size-preview-title";

    const stage = document.createElement("div");
    stage.className = "bubba-size-preview-stage";

    previewRect = document.createElement("div");
    previewRect.className = "bubba-size-preview-rect";
    stage.appendChild(previewRect);

    previewMeta = document.createElement("div");
    previewMeta.className = "bubba-size-preview-meta";

    previewPanel.appendChild(previewTitle);
    previewPanel.appendChild(stage);
    previewPanel.appendChild(previewMeta);
    document.body.appendChild(previewPanel);
}

function hidePreviewPanel() {
    if (previewPanel) {
        previewPanel.classList.remove("is-visible");
    }
}

function parseDimensionsFromValue(value) {
    const text = String(value || "");
    const match = text.match(/(\d+)\s*x\s*(\d+)/i);
    if (!match) {
        return null;
    }
    const width = Number.parseInt(match[1], 10);
    const height = Number.parseInt(match[2], 10);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        return null;
    }
    return { width, height };
}

function gcd(a, b) {
    let x = Math.abs(a);
    let y = Math.abs(b);
    while (y) {
        const t = y;
        y = x % y;
        x = t;
    }
    return x || 1;
}

function ratioLabel(width, height) {
    const d = gcd(width, height);
    return `${Math.round(width / d)}:${Math.round(height / d)}`;
}

function getMpLabel(rawValue) {
    const dims = parseDimensionsFromValue(rawValue);
    if (!dims) {
        return "";
    }
    const mp = (dims.width * dims.height) / 1_000_000;
    return `${mp.toFixed(2)}MP`;
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

function showPreviewForEntry(entryElement) {
    ensurePreviewPanel();
    if (!previewPanel || !previewRect || !previewTitle || !previewMeta) {
        return;
    }

    const rawValue = entryElement?.dataset?.valueForPreview || entryElement?.getAttribute("data-value") || entryElement?.textContent || "";
    const dims = parseDimensionsFromValue(rawValue);
    if (!dims) {
        hidePreviewPanel();
        return;
    }

    const maxBox = 168;
    const scale = maxBox / 1536;
    const renderW = Math.max(24, Math.round(dims.width * scale));
    const renderH = Math.max(24, Math.round(dims.height * scale));

    previewRect.style.width = `${renderW}px`;
    previewRect.style.height = `${renderH}px`;

    const mp = (dims.width * dims.height) / 1_000_000;
    previewTitle.textContent = `${dims.width}x${dims.height}`;
    previewMeta.textContent = `${ratioLabel(dims.width, dims.height)} • ${mp.toFixed(2)}MP`;

    previewPanel.classList.add("is-visible");
    positionPreviewPanel(entryElement);
}

function bindEntryPreview(entryElement) {
    if (!entryElement || entryElement.dataset?.bubbaSizePreviewBound === "1") {
        return;
    }
    entryElement.dataset.bubbaSizePreviewBound = "1";

    entryElement.addEventListener("mouseenter", () => {
        showPreviewForEntry(entryElement);
    });

    entryElement.addEventListener("mouseleave", () => {
        hidePreviewPanel();
    });
}

function bindEntrySelectionTracking(entryElement) {
    if (!entryElement || entryElement.dataset?.bubbaSizeSelectionBound === "1") {
        return;
    }
    entryElement.dataset.bubbaSizeSelectionBound = "1";

    entryElement.addEventListener("click", () => {
        pushRecentValue(entryElement.dataset?.valueForPreview || entryElement.getAttribute("data-value") || "");
        hidePreviewPanel();
    });
}

function parseGroupAndLabel(rawValue) {
    const text = String(rawValue || "");
    const sep = text.indexOf(" | ");
    if (sep < 0) {
        return { group: null, displayLabel: text };
    }
    return { group: text.slice(0, sep), displayLabel: text.slice(sep + 3) };
}

function isHeadingValue(rawValue) {
    // Kept for widget value guard — headings are no longer real list entries.
    const text = String(rawValue || "").trim();
    return text.startsWith("---") && text.endsWith("---");
}

function formatHeading(rawValue) {
    const text = String(rawValue || "").trim();
    return text.replace(/^---\s*/, "").replace(/\s*---$/, "");
}

function parseDisplayParts(displayLabel) {
    const text = String(displayLabel || "").trim();
    const sep = text.indexOf(" - ");
    if (sep < 0) {
        return { dimensions: text, modelLabel: "" };
    }
    return {
        dimensions: text.slice(0, sep),
        modelLabel: text.slice(sep + 3),
    };
}

function ensureEntryLayout(entry, rawValue) {
    if (!entry || entry.dataset?.bubbaSizeLayoutApplied === "1") {
        return;
    }
    entry.dataset.bubbaSizeLayoutApplied = "1";

    const { displayLabel } = parseGroupAndLabel(rawValue);
    const { dimensions, modelLabel } = parseDisplayParts(displayLabel);

    const main = document.createElement("span");
    main.className = "bubba-size-option";

    const mainInfo = document.createElement("span");
    mainInfo.className = "bubba-size-option-main";

    const label = document.createElement("span");
    label.className = "bubba-size-option-label";
    label.textContent = dimensions;

    const mpPill = document.createElement("span");
    mpPill.className = "bubba-size-mp-pill";
    mpPill.textContent = getMpLabel(rawValue);

    const modelPill = document.createElement("span");
    modelPill.className = "bubba-size-model-pill";
    modelPill.textContent = modelLabel;

    while (entry.firstChild) {
        entry.removeChild(entry.firstChild);
    }

    mainInfo.appendChild(label);
    main.appendChild(mainInfo);
    if (modelLabel) {
        main.appendChild(modelPill);
    }
    if (mpPill.textContent) {
        main.appendChild(mpPill);
    }
    entry.appendChild(main);
}

function bindEntryFavoriteButton(entryElement) {
    if (!entryElement || entryElement.dataset?.bubbaSizeFavoriteBound === "1") {
        return;
    }
    entryElement.dataset.bubbaSizeFavoriteBound = "1";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "bubba-size-fav-btn";
    button.title = "Toggle favorite";

    const syncState = () => {
        const value = entryElement.dataset?.valueForPreview || entryElement.getAttribute("data-value") || "";
        const on = isFavoriteValue(value);
        button.classList.toggle("is-on", on);
        button.textContent = on ? "★" : "☆";
    };

    syncState();
    const row = entryElement.querySelector(".bubba-size-option") || entryElement;
    row.appendChild(button);

    button.addEventListener("mousedown", (event) => {
        event.preventDefault();
        event.stopPropagation();
    });

    button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();

        const value = entryElement.dataset?.valueForPreview || entryElement.getAttribute("data-value") || "";
        toggleFavoriteValue(value);

        if (!activeMenu?.isConnected) {
            syncState();
            return;
        }

        for (const btn of activeMenu.querySelectorAll(".bubba-size-fav-btn")) {
            const owner = btn.closest(".litemenu-entry");
            const ownerValue = owner?.dataset?.valueForPreview || owner?.getAttribute("data-value") || "";
            const on = isFavoriteValue(ownerValue);
            btn.classList.toggle("is-on", on);
            btn.textContent = on ? "★" : "☆";
        }
    });
}

function buildQuickSection(title, values, entryByValue) {
    return createQuickSection({
        title,
        values,
        entryByValue,
        headerClass: "bubba-size-quick-header",
        createItem(value, sourceEntry) {
            const quickItem = document.createElement("div");
            quickItem.className = "litemenu-entry bubba-size-quick-item";
            quickItem.setAttribute("data-value", value);
            quickItem.dataset.valueForPreview = value;
            ensureEntryLayout(quickItem, value);
            bindEntryPreview(quickItem);
            bindEntryFavoriteButton(quickItem);
            quickItem.addEventListener("click", (event) => {
                if (!event.defaultPrevented) {
                    sourceEntry.click();
                }
            });
            return quickItem;
        },
    });
}

function buildSizeMenu(menu, selectedValue = "") {
    activeMenu = menu;
    menu.classList.add("bubba-size-menu");

    const entries = Array.from(menu.querySelectorAll(".litemenu-entry"));
    const selectedNormalized = String(selectedValue || "").trim();
    const entryByValue = new Map();
    let rootContainer = null;
    const groups = [];
    let selectedGroup = null;
    const groupsByName = new Map();

    for (const entry of entries) {
        const rawValue = entry.getAttribute("data-value") || entry.textContent || "";
        const { group: groupName } = parseGroupAndLabel(rawValue);

        if (!groupName) {
            continue;
        }

        if (!rootContainer) {
            rootContainer = entry.parentElement;
        }

        // Build group heading on first encounter.
        if (!groupsByName.has(groupName)) {
            const headingEntry = document.createElement("div");
            headingEntry.className = "litemenu-entry bubba-size-heading";

            const textSpan = document.createElement("span");
            textSpan.className = "bubba-size-heading-text";
            textSpan.textContent = groupName;
            const chevron = document.createElement("span");
            chevron.className = "bubba-size-chevron";
            headingEntry.appendChild(textSpan);
            headingEntry.appendChild(chevron);

            // Insert heading immediately before the first entry in this group.
            entry.parentElement.insertBefore(headingEntry, entry);

            const group = { headingEntry, heading: groupName, presetEntries: [] };
            groupsByName.set(groupName, group);
            groups.push(group);
        }

        const group = groupsByName.get(groupName);
        group.presetEntries.push(entry);

        entry.classList.remove("bubba-size-heading");
        if (selectedNormalized && String(rawValue).trim() === selectedNormalized) {
            entry.classList.add("bubba-size-selected");
            selectedGroup = group;
        }

        entry.dataset.valueForPreview = rawValue;
        entryByValue.set(rawValue, entry);

        ensureEntryLayout(entry, rawValue);
        bindEntryPreview(entry);
        bindEntrySelectionTracking(entry);
        bindEntryFavoriteButton(entry);
    }

    const expandedGroups = getExpandedGroups();
    for (const group of groups) {
        const isSelected = group === selectedGroup;
        makeHeadingCollapsible(group.headingEntry, group.presetEntries, group.heading, !isSelected && !expandedGroups.has(group.heading));
    }

    if (!rootContainer) {
        return;
    }

    const favorites = getFavoriteValues().filter((value) => entryByValue.has(value));
    const recents = getRecentValues().filter((value) => entryByValue.has(value) && !favorites.includes(value));

    const recentSection = buildQuickSection("Recent", recents.slice(0, SIZE_MENU_RECENTS_LIMIT), entryByValue);
    const favoriteSection = buildQuickSection("Favorites", favorites, entryByValue);

    if (recentSection) {
        rootContainer.prepend(recentSection);
    }
    if (favoriteSection) {
        rootContainer.prepend(favoriteSection);
    }

    setupKeyboardNavigation(menu, {
        boundDatasetKey: "bubbaSizeKeyboardBound",
        headerClass: "bubba-size-quick-header",
        skipClassNames: ["bubba-size-heading"],
        focusClass: "bubba-size-focused",
        selectedSelector: ".bubba-size-selected",
    });
}

function isTargetWidget(node, widget) {
    return !!node && node.comfyClass === TARGET_NODE_CLASS && widget?.name === TARGET_WIDGET_NAME;
}

const ensureMenuObserver = installLiteMenuObserver({
    app,
    isTargetNode(node) {
        return !!node && node.comfyClass === TARGET_NODE_CLASS;
    },
    isTargetWidget(node, widget) {
        return isTargetWidget(node, widget);
    },
    onMenuOpen(menu, node, widget) {
        buildSizeMenu(menu, String(widget?.value ?? ""));
    },
    onMenuClose() {
        hidePreviewPanel();
    },
});

function installEmptyLatentSizeMenu() {
    installStyles();
    ensureMenuObserver();

    app.registerExtension({
        name: EXTENSION_NAME,
        beforeRegisterNodeDef(nodeType, nodeData) {
            if (nodeData?.name !== TARGET_NODE_CLASS) {
                return;
            }

            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function onNodeCreatedWithSizeMenu() {
                const result = typeof originalOnNodeCreated === "function"
                    ? originalOnNodeCreated.apply(this, arguments)
                    : undefined;

                const widget = this.widgets?.find((w) => w.name === TARGET_WIDGET_NAME);
                if (widget) {
                    let _value = widget.value;
                    Object.defineProperty(widget, "value", {
                        configurable: true,
                        get() {
                            return _value;
                        },
                        set(incoming) {
                            if (!isHeadingValue(incoming)) {
                                _value = incoming;
                            }
                        },
                    });
                }

                return result;
            };
        },
    });
}

export {
    installEmptyLatentSizeMenu,
};
