// Main entry point for autocomplete module - re-exports public API

export { BubbaTextAutoComplete, installStringWidgetHook } from './autocomplete/ui.js';
export { ensureEmbeddingCacheSeeded, ensureWildcardCacheSeeded } from './autocomplete/cache.js';
export { ensureLocalCsvCacheSeeded, exportLocalTagCacheCsv, refreshLocalCsvCache, clearLocalTagCache, parseLocalTagCacheStatus } from './autocomplete/csv.js';
export {
	PROMPT_SNIPPETS_KEY,
	readPromptSnippets,
	savePromptSnippet,
	deletePromptSnippet,
	normalizeSnippetName,
	exportPromptSnippetsJson,
	importPromptSnippetsJson,
	replacePromptSnippets,
} from './autocomplete/snippets.js';
