// UI component for text autocomplete

import { getDanbooruCategoryLabel, formatNumber, getSearchQueryVariations } from './utils.js';
import { getSearchIndex, findMatchesFromIndex, findMatchMetadata } from './search.js';
import { getWordList, ensureEmbeddingCacheSeeded } from './cache.js';

// Styles
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
	if (typeof document !== "undefined") {
		document.body.appendChild(style);
	}
}

export class BubbaTextAutoComplete {
	constructor(inputEl, group) {
		this.inputEl = inputEl;
		this.group = group || "common";
		this.menuEl = document.createElement("div");
		this.menuEl.classList.add("bubba-autocomplete");
		document.body.appendChild(this.menuEl);
		this.menuEl.style.display = "none";
		this.items = [];
		this.selectedIndex = -1;
		this.searchDebounceMs = 16;
		this.searchTimer = null;
		this.latestQuery = "";
		this.previousQuery = "";
		this.previousMatchedPool = null;
		this.embeddingWarmupInFlight = false;
		this.searchInFlight = false;
		this.currentSearchRevision = 0;
		this.pendingSearchRevision = 0;

		this.onInput = this.onInput.bind(this);
		this.onInputImmediate = this.onInputImmediate.bind(this);
		this.performSearchAsync = this.performSearchAsync.bind(this);
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
		if (this.searchDebounceMs <= 0) {
			this.onInputImmediate();
			return;
		}
		this.searchTimer = setTimeout(this.onInputImmediate, this.searchDebounceMs);
	}

	onInputImmediate() {
		if (!BubbaTextAutoComplete.enabled) {
			this.hide();
			return;
		}

		if (!this.embeddingWarmupInFlight) {
			this.embeddingWarmupInFlight = true;
			ensureEmbeddingCacheSeeded()
				.then((loaded) => {
					this.embeddingWarmupInFlight = false;
					if (!loaded || document.activeElement !== this.inputEl) {
						return;
					}
					if (!this.getQuery().query) {
						return;
					}
					this.onInputImmediate();
				})
				.catch(() => {
					this.embeddingWarmupInFlight = false;
				});
		}

		const { query } = this.getQuery();
		if (!query) {
			this.latestQuery = "";
			this.previousQuery = "";
			this.previousMatchedPool = null;
			this.hide();
			return;
		}

		this.latestQuery = query;

		// Schedule search asynchronously to keep UI responsive
		this.pendingSearchRevision += 1;
		const searchRevision = this.pendingSearchRevision;
		this.scheduleAsyncSearch(query, searchRevision);
	}

	scheduleAsyncSearch(query, searchRevision) {
		if (typeof requestAnimationFrame !== "undefined") {
			requestAnimationFrame(() => this.performSearchAsync(query, searchRevision));
		} else {
			setTimeout(() => this.performSearchAsync(query, searchRevision), 0);
		}
	}

	performSearchAsync(query, searchRevision) {
		// Skip if a newer search has already been scheduled
		if (searchRevision < this.pendingSearchRevision) {
			return;
		}

		// Skip if another search is already in flight (shouldn't happen, but be safe)
		if (this.searchInFlight) {
			return;
		}

		this.searchInFlight = true;

		try {
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

			// Only show results if this is still the latest search
			if (searchRevision === this.pendingSearchRevision && document.activeElement === this.inputEl) {
				this.show(results);
			}

			this.currentSearchRevision = searchRevision;
		} finally {
			this.searchInFlight = false;
			// Ensure we process the latest query if keystrokes happened while searching.
			if (this.currentSearchRevision < this.pendingSearchRevision && this.latestQuery) {
				const latestRevision = this.pendingSearchRevision;
				this.scheduleAsyncSearch(this.latestQuery, latestRevision);
			}
		}
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
BubbaTextAutoComplete.suggestionLimit = 20;

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

export function installStringWidgetHook() {
	try {
		const ComfyWidgets = window.comfyAPI?.widgets?.ComfyWidgets;
		if (!ComfyWidgets) {
			console.warn("Bubba Autocomplete: ComfyWidgets not available");
			return;
		}

		const original = ComfyWidgets.STRING;
		if (!original) {
			console.warn("Bubba Autocomplete: ComfyWidgets.STRING not available");
			return;
		}
		if (original?.__bubbaAutoCompletePatched) {
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
	} catch (error) {
		console.error("Bubba Autocomplete: Failed to install string widget hook:", error);
	}
}
