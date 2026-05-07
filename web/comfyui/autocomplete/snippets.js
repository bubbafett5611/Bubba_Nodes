const PROMPT_SNIPPETS_KEY = "bubba.PromptSnippets";

function normalizeSnippetName(value) {
	return String(value || "")
		.trim()
		.toLowerCase()
		.replace(/\s+/g, "_")
		.replace(/[^a-z0-9_-]/g, "");
}

function normalizeSnippetRecord(snippet) {
	if (!snippet || typeof snippet !== "object") {
		return null;
	}

	const name = normalizeSnippetName(snippet.name);
	const text = String(snippet.text || "").trim();
	if (!name || !text) {
		return null;
	}

	const category = String(snippet.category || "").trim();
	return {
		name,
		text,
		category,
	};
}

function sortSnippets(snippets) {
	return [...snippets].sort((a, b) => a.name.localeCompare(b.name));
}

function readPromptSnippets() {
	const raw = localStorage.getItem(PROMPT_SNIPPETS_KEY);
	if (!raw) {
		return [];
	}

	try {
		const parsed = JSON.parse(raw);
		if (!Array.isArray(parsed)) {
			return [];
		}
		return sortSnippets(parsed.map(normalizeSnippetRecord).filter(Boolean));
	} catch {
		return [];
	}
}

function writePromptSnippets(snippets) {
	localStorage.setItem(PROMPT_SNIPPETS_KEY, JSON.stringify(sortSnippets(snippets)));
}

function replacePromptSnippets(snippets) {
	const normalized = Array.isArray(snippets) ? snippets.map(normalizeSnippetRecord).filter(Boolean) : [];
	writePromptSnippets(normalized);
	return sortSnippets(normalized);
}

function savePromptSnippet(snippet, previousName = "") {
	const normalized = normalizeSnippetRecord(snippet);
	if (!normalized) {
		throw new Error("invalid_snippet");
	}

	const current = readPromptSnippets();
	const previousKey = normalizeSnippetName(previousName);
	const filtered = current.filter((item) => item.name !== normalized.name && item.name !== previousKey);
	filtered.push(normalized);
	writePromptSnippets(filtered);
	return normalized;
}

function deletePromptSnippet(name) {
	const target = normalizeSnippetName(name);
	if (!target) {
		return;
	}
	writePromptSnippets(readPromptSnippets().filter((item) => item.name !== target));
}

function findPromptSnippetsByQuery(query, limit = 20) {
	const needle = normalizeSnippetName(String(query || "").replace(/^@+/, ""));
	const snippets = readPromptSnippets();
	if (!needle) {
		return snippets.slice(0, Math.max(0, limit));
	}
	const startsWith = [];
	const contains = [];
	for (const snippet of snippets) {
		if (snippet.name.startsWith(needle)) {
			startsWith.push(snippet);
			continue;
		}
		if (snippet.name.includes(needle)) {
			contains.push(snippet);
		}
	}

	return [...startsWith, ...contains].slice(0, Math.max(0, limit));
}

function exportPromptSnippetsJson() {
	return JSON.stringify(readPromptSnippets(), null, 2);
}

function importPromptSnippetsJson(raw, { mode = "merge" } = {}) {
	const parsed = JSON.parse(String(raw || "[]"));
	if (!Array.isArray(parsed)) {
		throw new Error("invalid_snippet_file");
	}

	const incoming = parsed.map(normalizeSnippetRecord).filter(Boolean);
	if (mode === "replace") {
		return replacePromptSnippets(incoming);
	}

	const mergedByName = new Map(readPromptSnippets().map((snippet) => [snippet.name, snippet]));
	for (const snippet of incoming) {
		mergedByName.set(snippet.name, snippet);
	}
	const merged = [...mergedByName.values()];
	writePromptSnippets(merged);
	return sortSnippets(merged);
}

export {
	deletePromptSnippet,
	exportPromptSnippetsJson,
	findPromptSnippetsByQuery,
	importPromptSnippetsJson,
	normalizeSnippetName,
	PROMPT_SNIPPETS_KEY,
	readPromptSnippets,
	replacePromptSnippets,
	savePromptSnippet,
};
