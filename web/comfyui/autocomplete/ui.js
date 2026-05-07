// UI component for text autocomplete

import { getDanbooruCategoryLabel, formatNumber, getSearchQueryVariations } from './utils.js';
import { getSearchIndex, findMatchesFromIndex, findMatchMetadata } from './search.js';
import { getWordList, ensureEmbeddingCacheSeeded } from './cache.js';

const WORKER_RESPONSE_TIMEOUT_MS = 10000;
const PROMPT_CHIP_LIMIT = 36;
const PROMPT_CONFLICT_RULES = [
	{ terms: ["solo", "multiple people"], severity: "hard" },
	{ terms: ["solo", "group"], severity: "hard" },
	{ terms: ["solo", "crowd"], severity: "hard" },
	{ terms: ["day", "night"], severity: "hard" },
	{ terms: ["indoors", "outdoors"], severity: "hard" },
	{ terms: ["inside", "outside"], severity: "hard" },
	{ terms: ["eyes open", "closed eyes"], severity: "hard" },
	{ terms: ["front view", "back view"], severity: "hard" },
	{ terms: ["safe", "nsfw"], severity: "hard" },
	{ terms: ["sfw", "nsfw"], severity: "hard" },
	{ terms: ["solo", "male", "female"], severity: "soft" },
	{ terms: ["solo", "1girl", "1boy"], severity: "soft" },
	{ terms: ["realistic", "anime"], severity: "soft" },
	{ terms: ["photorealistic", "anime"], severity: "soft" },
	{ terms: ["full body", "close-up"], severity: "soft" },
	{ terms: ["full body", "portrait"], severity: "soft" },
	{ terms: ["standing", "sitting"], severity: "soft" },
	{ terms: ["standing", "lying"], severity: "soft" },
	{ terms: ["smile", "crying"], severity: "soft" },
	{ terms: ["young", "old"], severity: "soft" },
];

const promptAssistantInstancesByNode = new WeakMap();

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
		.bubba-prompt-assistant {
			position: fixed;
			z-index: 99998;
			display: flex;
			flex-wrap: wrap;
			gap: 4px;
			align-items: center;
			box-sizing: border-box;
			width: max-content;
			max-width: min(460px, calc(100vw - 16px));
			padding: 3px 6px;
			border: 1px solid rgba(128, 128, 128, 0.28);
			border-radius: 6px;
			background: var(--comfy-menu-bg);
			background: color-mix(in srgb, var(--comfy-menu-bg) 92%, transparent);
			pointer-events: none;
			font-size: 11px;
			line-height: 1.2;
			overflow: hidden;
		}
		.bubba-prompt-assistant[hidden] {
			display: none;
		}
		.bubba-prompt-chip {
			max-width: 180px;
			padding: 2px 6px;
			border: 1px solid rgba(128, 128, 128, 0.35);
			border-radius: 4px;
			background: rgba(128, 128, 128, 0.12);
			color: var(--input-text);
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.bubba-prompt-chip.issue {
			border-color: rgba(255, 176, 64, 0.75);
			background: rgba(255, 176, 64, 0.16);
		}
		.bubba-prompt-chip.warning {
			border-color: rgba(255, 205, 80, 0.82);
			background: rgba(255, 205, 80, 0.18);
		}
		.bubba-prompt-chip.conflict {
			border-color: rgba(255, 90, 90, 0.75);
			background: rgba(255, 90, 90, 0.16);
		}
		.bubba-prompt-chip.shared {
			border-color: rgba(120, 170, 255, 0.65);
			background: rgba(120, 170, 255, 0.14);
		}
		.bubba-prompt-summary {
			opacity: 0.78;
			padding: 2px 4px;
		}
	`;
	if (typeof document !== "undefined") {
		document.body.appendChild(style);
	}
}

function normalizePromptToken(value) {
	return String(value || "")
		.replace(/\s+/g, " ")
		.trim()
		.toLowerCase();
}

function splitPromptTokens(value) {
	return String(value || "")
		.replace(/\n/g, ",")
		.split(",")
		.map((part) => part.trim())
		.filter(Boolean);
}

function estimatePromptTokenCount(value) {
	const words = String(value || "").match(/[A-Za-z0-9]+(?:[_'-][A-Za-z0-9]+)*/g);
	return Array.isArray(words) ? words.length : 0;
}

function analyzePromptText(value) {
	const tokens = splitPromptTokens(value);
	const counts = new Map();
	for (const token of tokens) {
		const key = normalizePromptToken(token);
		if (!key) {
			continue;
		}
		counts.set(key, (counts.get(key) || 0) + 1);
	}

	const duplicates = new Set([...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key));
	const localConflicts = [];
	for (const rule of PROMPT_CONFLICT_RULES) {
		if (rule.terms.every((term) => counts.has(term))) {
			localConflicts.push({
				text: rule.terms.join(" + "),
				severity: rule.severity,
			});
		}
	}

	return {
		tokens,
		counts,
		duplicates,
		localConflicts,
		estimatedTokenCount: estimatePromptTokenCount(value),
	};
}

function resolvePromptRole(group, inputName) {
	const key = `${group || ""} ${inputName || ""}`.toLowerCase();
	if (key.includes("negative")) {
		return "negative";
	}
	return "positive";
}

function getNodeAssistantInstances(node) {
	if (!node || typeof node !== "object") {
		return [];
	}
	return promptAssistantInstancesByNode.get(node) || [];
}

function registerPromptAssistantInstance(node, instance) {
	if (!node || typeof node !== "object") {
		return;
	}
	const instances = getNodeAssistantInstances(node);
	if (!instances.includes(instance)) {
		instances.push(instance);
		promptAssistantInstancesByNode.set(node, instances);
	}
}

function unregisterPromptAssistantInstance(node, instance) {
	if (!node || typeof node !== "object") {
		return;
	}
	const instances = getNodeAssistantInstances(node);
	const nextInstances = instances.filter((item) => item !== instance);
	if (nextInstances.length) {
		promptAssistantInstancesByNode.set(node, nextInstances);
		return;
	}
	promptAssistantInstancesByNode.delete(node);
}

function collectNodeRoleTokens(node) {
	const roles = {
		positive: new Set(),
		negative: new Set(),
	};
	for (const instance of getNodeAssistantInstances(node)) {
		const analysis = instance.getPromptAnalysis();
		for (const key of analysis.counts.keys()) {
			roles[instance.promptRole].add(key);
		}
	}
	return roles;
}

function findCrossPromptConflicts(node, role, analysis) {
	if (!node || !analysis.tokens.length) {
		return new Set();
	}
	const roles = collectNodeRoleTokens(node);
	const oppositeRole = role === "negative" ? "positive" : "negative";
	const opposite = roles[oppositeRole] || new Set();
	const conflicts = new Set();
	for (const key of analysis.counts.keys()) {
		if (opposite.has(key)) {
			conflicts.add(key);
		}
	}
	return conflicts;
}

function promptAssistantSummaryParts(role, analysis, crossConflicts) {
	const parts = [];
	const hardConflictCount = analysis.localConflicts.filter((conflict) => conflict.severity === "hard").length;
	const softWarningCount = analysis.localConflicts.filter((conflict) => conflict.severity !== "hard").length;
	if (analysis.duplicates.size) {
		parts.push(`${analysis.duplicates.size} duplicate${analysis.duplicates.size === 1 ? "" : "s"}`);
	}
	if (crossConflicts.size) {
		parts.push(`${crossConflicts.size} shared with ${role === "negative" ? "positive" : "negative"}`);
	}
	if (hardConflictCount) {
		parts.push(`${hardConflictCount} conflict${hardConflictCount === 1 ? "" : "s"}`);
	}
	if (softWarningCount) {
		parts.push(`${softWarningCount} warning${softWarningCount === 1 ? "" : "s"}`);
	}
	return parts;
}

function buildPromptIssueChips(role, analysis, crossConflicts) {
	const chips = [];
	const oppositeRole = role === "negative" ? "positive" : "negative";
	const seen = new Set();

	for (const token of analysis.tokens) {
		const key = normalizePromptToken(token);
		if (!key || seen.has(key)) {
			continue;
		}
		if (analysis.duplicates.has(key)) {
			seen.add(key);
			chips.push({
				text: token,
				kind: "duplicate",
			});
			continue;
		}
		if (crossConflicts.has(key)) {
			seen.add(key);
			chips.push({
				text: token,
				kind: "shared",
				title: `Also in ${oppositeRole}`,
			});
		}
	}

	for (const conflict of analysis.localConflicts) {
		chips.push({
			text: conflict.text,
			kind: conflict.severity === "hard" ? "conflict" : "warning",
		});
	}

	return chips;
}

export class BubbaTextAutoComplete {
	constructor(inputEl, group, node = null, inputName = "") {
		this.inputEl = inputEl;
		this.group = group || "common";
		this.node = node;
		this.inputName = inputName || "";
		this.promptRole = resolvePromptRole(this.group, this.inputName);
		this.menuEl = document.createElement("div");
		this.menuEl.classList.add("bubba-autocomplete");
		document.body.appendChild(this.menuEl);
		this.assistantEl = document.createElement("div");
		this.assistantEl.classList.add("bubba-prompt-assistant");
		this.assistantEl.hidden = true;
		document.body.appendChild(this.assistantEl);
		this.menuEl.style.display = "none";
		this.items = [];
		this.selectedIndex = -1;
		this.searchDebounceMs = 0;
		this.searchTimer = null;
		this.latestQuery = "";
		this.previousQuery = "";
		this.previousMatchedPool = null;
		this.embeddingWarmupInFlight = false;
		this.searchInFlight = false;
		this.currentSearchRevision = 0;
		this.pendingSearchRevision = 0;
		this.searchWorker = null;
		this.searchWorkerEnabled = false;
		this.workerWordsRef = null;
		this.workerRequestSeq = 0;
		this.workerPending = new Map();
		this.inputWasConnected = this.inputEl.isConnected;
		this.promptAssistantBlurTimer = null;

		this.onInput = this.onInput.bind(this);
		this.onInputImmediate = this.onInputImmediate.bind(this);
		this.performSearchAsync = this.performSearchAsync.bind(this);
		this.onKeyDown = this.onKeyDown.bind(this);
		this.onBlur = this.onBlur.bind(this);
		this.onFocus = this.onFocus.bind(this);
		this.updatePromptAssistant = this.updatePromptAssistant.bind(this);
		this.requestPromptAssistantPosition = this.requestPromptAssistantPosition.bind(this);
		this.positionPromptAssistant = this.positionPromptAssistant.bind(this);

		this.inputEl.addEventListener("input", this.onInput);
		this.inputEl.addEventListener("keydown", this.onKeyDown);
		this.inputEl.addEventListener("blur", this.onBlur);
		this.inputEl.addEventListener("focus", this.onFocus);
		window.addEventListener("resize", this.requestPromptAssistantPosition);
		document.addEventListener("scroll", this.requestPromptAssistantPosition, true);
		document.addEventListener("pointermove", this.requestPromptAssistantPosition, { passive: true });
		document.addEventListener("wheel", this.requestPromptAssistantPosition, { passive: true });
		registerPromptAssistantInstance(this.node, this);
		this.initializeSearchWorker();
		this.updatePromptAssistant();
	}

	initializeSearchWorker() {
		if (typeof Worker === "undefined") {
			return;
		}
		try {
			this.searchWorker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
			this.searchWorkerEnabled = true;
			this.searchWorker.onmessage = (event) => {
				const message = event?.data || {};
				const pending = this.workerPending.get(message.requestId);
				if (!pending) {
					return;
				}
				this.workerPending.delete(message.requestId);
				if (message.type === "error") {
					pending.reject(new Error(String(message.error || "worker_error")));
					return;
				}
				pending.resolve(message);
			};
			this.searchWorker.onerror = (event) => {
				console.warn("Bubba Autocomplete: worker crashed, falling back to main-thread search.", event?.message || event);
				this.disableSearchWorker();
			};
			// Pre-warm: build the search index in the worker during idle time so it's ready before first keystroke
			const prewarm = () => this.syncWorkerWords(getWordList()).catch(() => {});
			if (typeof requestIdleCallback !== "undefined") {
				requestIdleCallback(prewarm, { timeout: 3000 });
			} else {
				setTimeout(prewarm, 500);
			}
		} catch (error) {
			console.warn("Bubba Autocomplete: failed to initialize worker, falling back to main-thread search.", error);
			this.disableSearchWorker();
		}
	}

	disableSearchWorker() {
		this.searchWorkerEnabled = false;
		this.workerWordsRef = null;
		if (this.searchWorker) {
			try {
				this.searchWorker.terminate();
			} catch {
				// ignore worker termination errors
			}
		}
		this.searchWorker = null;
		for (const pending of this.workerPending.values()) {
			pending.reject(new Error("worker_disabled"));
		}
		this.workerPending.clear();
	}

	destroy() {
		if (this.destroyed) {
			return;
		}
		this.destroyed = true;
		this.inputEl.removeEventListener("input", this.onInput);
		this.inputEl.removeEventListener("keydown", this.onKeyDown);
		this.inputEl.removeEventListener("blur", this.onBlur);
		this.inputEl.removeEventListener("focus", this.onFocus);
		window.removeEventListener("resize", this.requestPromptAssistantPosition);
		document.removeEventListener("scroll", this.requestPromptAssistantPosition, true);
		document.removeEventListener("pointermove", this.requestPromptAssistantPosition);
		document.removeEventListener("wheel", this.requestPromptAssistantPosition);
		if (this.promptAssistantPositionFrame) {
			cancelAnimationFrame(this.promptAssistantPositionFrame);
			this.promptAssistantPositionFrame = null;
		}
		if (this.promptAssistantBlurTimer) {
			clearTimeout(this.promptAssistantBlurTimer);
			this.promptAssistantBlurTimer = null;
		}
		unregisterPromptAssistantInstance(this.node, this);
		this.disableSearchWorker();
		this.menuEl.remove();
		this.assistantEl.remove();
	}

	postWorkerMessage(payload, timeoutMs = WORKER_RESPONSE_TIMEOUT_MS) {
		if (!this.searchWorkerEnabled || !this.searchWorker) {
			return Promise.reject(new Error("worker_unavailable"));
		}
		const requestId = ++this.workerRequestSeq;
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				this.workerPending.delete(requestId);
				reject(new Error("worker_timeout"));
			}, timeoutMs);
			this.workerPending.set(requestId, {
				resolve: (message) => {
					clearTimeout(timer);
					resolve(message);
				},
				reject: (error) => {
					clearTimeout(timer);
					reject(error);
				},
			});
			this.searchWorker.postMessage({ ...payload, requestId });
		});
	}

	async syncWorkerWords(words) {
		if (!this.searchWorkerEnabled || !this.searchWorker) {
			return false;
		}
		if (this.workerWordsRef === words) {
			return true;
		}
		await this.postWorkerMessage({ type: "syncWords", words });
		this.workerWordsRef = words;
		return true;
	}

	async queryWorker(words, queryVariations, limit) {
		await this.syncWorkerWords(words);
		const message = await this.postWorkerMessage({
			type: "query",
			queryVariations,
			limit,
		});
		return {
			results: Array.isArray(message.results) ? message.results : [],
		};
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
		const text = BubbaTextAutoComplete.replaceUnderscores ? item.text.replaceAll("_", " ") : item.text;
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
		this.updatePromptAssistant();
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

	compareMatches(a, b) {
		const aBucket = this.getMatchBucket(a.matchScore);
		const bBucket = this.getMatchBucket(b.matchScore);
		if (aBucket !== bBucket) {
			return bBucket - aBucket;
		}
		const aCount = typeof a.count === "number" ? a.count : -1;
		const bCount = typeof b.count === "number" ? b.count : -1;
		if (aCount !== bCount) {
			return bCount - aCount;
		}
		const aScore = Number.isFinite(a.matchScore) ? a.matchScore : 0;
		const bScore = Number.isFinite(b.matchScore) ? b.matchScore : 0;
		if (aScore !== bScore) {
			return bScore - aScore;
		}
		return a.text.localeCompare(b.text);
	}

	selectTopMatches(matched, limit) {
		if (limit <= 0 || !Array.isArray(matched) || matched.length === 0) {
			return [];
		}

		const top = [];
		for (const item of matched) {
			let inserted = false;
			for (let i = 0; i < top.length; i += 1) {
				if (this.compareMatches(item, top[i]) < 0) {
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

	onInput() {
		this.updatePromptAssistant();
		for (const instance of getNodeAssistantInstances(this.node)) {
			if (instance !== this) {
				instance.updatePromptAssistant();
			}
		}
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

		this.pendingSearchRevision += 1;
		const searchRevision = this.pendingSearchRevision;
		this.performSearchAsync(query, searchRevision);
	}

	async performSearchAsync(query, searchRevision) {
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
			let results = [];

			if (this.searchWorkerEnabled) {
				try {
					const workerResult = await this.queryWorker(words, queryVariations, BubbaTextAutoComplete.suggestionLimit);
					results = workerResult.results;
				} catch (error) {
					console.warn("Bubba Autocomplete: worker query failed, falling back to main-thread search.", error);
					this.disableSearchWorker();
				}
			}

			if (!this.searchWorkerEnabled) {
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
				);
				results = this.selectTopMatches(matched, BubbaTextAutoComplete.suggestionLimit);

				if (matched.length <= 3000) {
					this.previousQuery = query;
					this.previousMatchedPool = matched;
				} else {
					this.previousQuery = "";
					this.previousMatchedPool = null;
				}
			} else {
				this.previousQuery = "";
				this.previousMatchedPool = null;
			}

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
				queueMicrotask(() => this.performSearchAsync(this.latestQuery, latestRevision));
			}
		}
	}

	onFocus() {
		if (!BubbaTextAutoComplete.enabled) return;
		if (this.promptAssistantBlurTimer) {
			clearTimeout(this.promptAssistantBlurTimer);
			this.promptAssistantBlurTimer = null;
		}
		this.updatePromptAssistant();
		this.onInputImmediate();
	}

	onBlur() {
		if (this.searchTimer) {
			clearTimeout(this.searchTimer);
			this.searchTimer = null;
		}
		setTimeout(() => this.hide(), 100);
		this.promptAssistantBlurTimer = setTimeout(() => {
			this.promptAssistantBlurTimer = null;
			this.hidePromptAssistant();
		}, 120);
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

	getPromptAnalysis() {
		return analyzePromptText(this.inputEl.value);
	}

	inputWasDetached() {
		if (this.inputEl.isConnected) {
			this.inputWasConnected = true;
			return false;
		}
		return this.inputWasConnected;
	}

	hidePromptAssistant() {
		this.assistantEl.hidden = true;
		this.assistantEl.style.visibility = "hidden";
	}

	requestPromptAssistantPosition() {
		if (this.inputWasDetached()) {
			this.destroy();
			return;
		}
		if (!this.inputEl.isConnected || this.promptAssistantPositionFrame || this.assistantEl.hidden) {
			return;
		}
		this.promptAssistantPositionFrame = requestAnimationFrame(() => {
			this.promptAssistantPositionFrame = null;
			this.positionPromptAssistant();
		});
	}

	positionPromptAssistant() {
		if (this.inputWasDetached()) {
			this.destroy();
			return;
		}
		if (!this.inputEl.isConnected || this.assistantEl.hidden) {
			return;
		}

		const rect = this.inputEl.getBoundingClientRect();
		const isVisible = rect.width > 0
			&& rect.height > 0
			&& rect.bottom > 0
			&& rect.top < window.innerHeight
			&& rect.right > 0
			&& rect.left < window.innerWidth;

		if (!isVisible) {
			this.assistantEl.style.visibility = "hidden";
			return;
		}

		this.assistantEl.style.width = "max-content";
		const measuredWidth = Math.min(this.assistantEl.offsetWidth || 120, window.innerWidth - 16);
		const left = Math.max(8, Math.min(rect.left, window.innerWidth - measuredWidth - 8));
		const measuredHeight = this.assistantEl.offsetHeight || 28;
		const top = rect.top - measuredHeight - 4 >= 8
			? rect.top - measuredHeight - 4
			: Math.min(rect.bottom + 4, window.innerHeight - measuredHeight - 8);

		this.assistantEl.style.left = `${Math.round(left)}px`;
		this.assistantEl.style.top = `${Math.round(top)}px`;
		this.assistantEl.style.visibility = "visible";
	}

	updatePromptAssistant() {
		if (this.inputWasDetached()) {
			this.destroy();
			return;
		}
		if (!this.inputEl.isConnected) {
			this.hidePromptAssistant();
			return;
		}
		if (document.activeElement !== this.inputEl) {
			this.hidePromptAssistant();
			return;
		}
		if (!BubbaTextAutoComplete.promptAssistantEnabled) {
			this.hidePromptAssistant();
			return;
		}

		const analysis = this.getPromptAnalysis();
		const crossConflicts = findCrossPromptConflicts(this.node, this.promptRole, analysis);
		const issueChips = buildPromptIssueChips(this.promptRole, analysis, crossConflicts);
		const hasIssues = analysis.duplicates.size > 0 || analysis.localConflicts.length > 0 || crossConflicts.size > 0;
		const visibleIssues = issueChips.slice(0, PROMPT_CHIP_LIMIT);

		this.assistantEl.replaceChildren();
		if (!analysis.tokens.length) {
			this.hidePromptAssistant();
			return;
		}

		for (const issue of visibleIssues) {
			const chip = document.createElement("span");
			chip.classList.add("bubba-prompt-chip");
			if (issue.kind === "duplicate") {
				chip.classList.add("issue");
				chip.title = "Duplicate tag";
			}
			if (issue.kind === "shared") {
				chip.classList.add("shared");
				chip.title = issue.title || "Shared with the opposite prompt";
			}
			if (issue.kind === "warning") {
				chip.classList.add("warning");
				chip.title = "Prompt warning";
			}
			if (issue.kind === "conflict") {
				chip.classList.add("conflict");
				chip.title = issue.title || "Prompt conflict";
			}
			chip.textContent = issue.text;
			this.assistantEl.appendChild(chip);
		}

		if (issueChips.length > visibleIssues.length) {
			const summary = document.createElement("span");
			summary.classList.add("bubba-prompt-summary");
			summary.textContent = `+${issueChips.length - visibleIssues.length} more issues`;
			this.assistantEl.appendChild(summary);
		}

		const summary = document.createElement("span");
		summary.classList.add("bubba-prompt-summary");
		const parts = promptAssistantSummaryParts(this.promptRole, analysis, crossConflicts);
		const issueText = hasIssues ? ` - ${parts.join(" | ")}` : "";
		summary.textContent = `${analysis.tokens.length} tag${analysis.tokens.length === 1 ? "" : "s"} | ~${analysis.estimatedTokenCount} tokens${issueText}`;
		this.assistantEl.appendChild(summary);

		this.assistantEl.hidden = false;
		this.positionPromptAssistant();
	}
}

BubbaTextAutoComplete.enabled = true;
BubbaTextAutoComplete.suggestionLimit = 20;
BubbaTextAutoComplete.replaceUnderscores = false;
BubbaTextAutoComplete.promptAssistantEnabled = true;

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
			new BubbaTextAutoComplete(inputEl, group, node, inputName);
			return result;
		};

		ComfyWidgets.STRING.__bubbaAutoCompletePatched = true;
	} catch (error) {
		console.error("Bubba Autocomplete: Failed to install string widget hook:", error);
	}
}
