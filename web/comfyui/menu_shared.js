const CIVITAI_DOMAIN_KEY = "bubba.Civitai.Domain";
const CIVITAI_DOMAIN_KEEP = "keep";

function getWidgetValue(node, widgetName) {
	return node?.widgets?.find((widget) => widget?.name === widgetName)?.value;
}

function normalizeSlashes(value) {
	return String(value || "").replace(/\\/g, "/").trim();
}

function getPreferredCivitaiDomain() {
	return String(localStorage.getItem(CIVITAI_DOMAIN_KEY) || CIVITAI_DOMAIN_KEEP).trim() || CIVITAI_DOMAIN_KEEP;
}

function rewriteCivitaiUrl(url) {
	const rawUrl = String(url || "").trim();
	if (!rawUrl) {
		return null;
	}

	const preferredDomain = getPreferredCivitaiDomain();
	if (preferredDomain === CIVITAI_DOMAIN_KEEP) {
		return rawUrl;
	}

	try {
		const parsed = new URL(rawUrl);
		parsed.host = preferredDomain;
		parsed.protocol = "https:";
		return parsed.toString();
	} catch {
		return rawUrl;
	}
}

function basenameWithoutExtension(value) {
	const normalized = normalizeSlashes(value);
	if (!normalized) {
		return "";
	}
	const leaf = normalized.split("/").pop() || normalized;
	const dotIndex = leaf.lastIndexOf(".");
	return dotIndex > 0 ? leaf.slice(0, dotIndex) : leaf;
}

function createQuickSection({
	title,
	values,
	entryByValue,
	headerClass,
	createItem,
}) {
	if (!Array.isArray(values) || !values.length) {
		return null;
	}

	const fragment = document.createDocumentFragment();
	const header = document.createElement("div");
	header.className = `litemenu-entry ${headerClass}`;
	header.textContent = title;
	fragment.appendChild(header);

	for (const value of values) {
		const sourceEntry = entryByValue.get(value);
		if (!sourceEntry) {
			continue;
		}
		const quickItem = createItem(value, sourceEntry);
		if (quickItem) {
			fragment.appendChild(quickItem);
		}
	}

	return fragment;
}

function setupKeyboardNavigation(menu, {
	boundDatasetKey,
	headerClass,
	skipClassNames = [],
	focusClass,
	selectedSelector,
	folderClass,
	folderArrowSelector,
	folderCollapsedGlyph = "▶",
	folderExpandedGlyph = "▼",
}) {
	if (!menu || menu.dataset?.[boundDatasetKey] === "1") {
		return;
	}
	menu.dataset[boundDatasetKey] = "1";

	const selectableEntries = () => Array.from(menu.querySelectorAll(".litemenu-entry"))
		.filter((entry) => !entry.classList.contains(headerClass))
		.filter((entry) => !skipClassNames.some((className) => entry.classList.contains(className)))
		.filter((entry) => entry.offsetParent !== null);

	let focusedEntry = null;
	const setFocusedEntry = (entry) => {
		if (focusedEntry && focusedEntry !== entry) {
			focusedEntry.classList.remove(focusClass);
		}
		focusedEntry = entry || null;
		if (focusedEntry) {
			focusedEntry.classList.add(focusClass);
			if (typeof focusedEntry.scrollIntoView === "function") {
				focusedEntry.scrollIntoView({ block: "nearest" });
			}
		}
	};

	const chooseInitialFocus = () => {
		const preferred = menu.querySelector(selectedSelector);
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
		if (event.key === "ArrowRight" && focusedEntry?.classList?.contains(folderClass)) {
			event.preventDefault();
			const arrow = focusedEntry.querySelector(folderArrowSelector);
			if (arrow?.textContent === folderCollapsedGlyph) {
				focusedEntry.click();
			}
			return;
		}
		if (event.key === "ArrowLeft" && focusedEntry?.classList?.contains(folderClass)) {
			event.preventDefault();
			const arrow = focusedEntry.querySelector(folderArrowSelector);
			if (arrow?.textContent === folderExpandedGlyph) {
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

function positionMenuNearCursor(menu, app, {
	offset = 10,
	margin = 10,
} = {}) {
	let left = app.canvas.last_mouse[0] - offset;
	let top = app.canvas.last_mouse[1] - offset;

	const bodyRect = document.body.getBoundingClientRect();
	const menuRect = menu.getBoundingClientRect();

	if (bodyRect.width && left > bodyRect.width - menuRect.width - margin) {
		left = bodyRect.width - menuRect.width - margin;
	}
	if (bodyRect.height && top > bodyRect.height - menuRect.height - margin) {
		top = bodyRect.height - menuRect.height - margin;
	}

	menu.style.left = `${left}px`;
	menu.style.top = `${top}px`;
}

function makeHeadingCollapsible({
	headingEntry,
	controlledEntries,
	isCollapsed,
	onToggle,
	chevronSelector,
	expandedGlyph = "▾",
	collapsedClass = "is-collapsed",
}) {
	if (!headingEntry) {
		return;
	}

	const chevron = headingEntry.querySelector(chevronSelector);
	if (chevron) {
		chevron.textContent = expandedGlyph;
	}

	const applyState = (collapsed) => {
		for (const entry of controlledEntries) {
			entry.style.display = collapsed ? "none" : "";
		}
		headingEntry.classList.toggle(collapsedClass, collapsed);
	};

	applyState(isCollapsed);
	headingEntry.removeAttribute("data-value");

	for (const eventName of ["mousedown", "mouseup", "pointerdown", "pointerup"]) {
		headingEntry.addEventListener(eventName, (event) => {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
		});
	}

	headingEntry.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
		const nextCollapsed = onToggle();
		applyState(nextCollapsed);
	});
}

function installLiteMenuObserver({
	app,
	isTargetNode,
	isTargetWidget,
	onMenuOpen,
	onMenuClose,
}) {
	let installed = false;

	return function ensureObserver() {
		if (installed) {
			return;
		}
		installed = true;

		const observer = new MutationObserver((mutations) => {
			const node = app.canvas.current_node;
			if (!isTargetNode(node)) {
				return;
			}

			for (const mutation of mutations) {
				for (const removed of mutation.removedNodes) {
					if (removed.classList?.contains("litecontextmenu")) {
						onMenuClose?.(removed, node);
					}
				}
				for (const added of mutation.addedNodes) {
					if (!added.classList?.contains("litecontextmenu")) {
						continue;
					}

					const widget = app.canvas.getWidgetAtCursor();
					if (!isTargetWidget(node, widget)) {
						continue;
					}

					requestAnimationFrame(() => {
						if (!added.querySelector(".comfy-context-menu-filter")) {
							return;
						}
						onMenuOpen(added, node, widget);
					});
					return;
				}
			}
		});

		observer.observe(document.body, { childList: true, subtree: false });
	};
}

export {
	basenameWithoutExtension,
	CIVITAI_DOMAIN_KEEP,
	CIVITAI_DOMAIN_KEY,
	createQuickSection,
	getWidgetValue,
	getPreferredCivitaiDomain,
	installLiteMenuObserver,
	makeHeadingCollapsible,
	normalizeSlashes,
	positionMenuNearCursor,
	rewriteCivitaiUrl,
	setupKeyboardNavigation,
};
