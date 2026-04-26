// Main entry point for autocomplete module - re-exports public API

export { BubbaTextAutoComplete, installStringWidgetHook } from './autocomplete/ui.js';
export { ensureEmbeddingCacheSeeded } from './autocomplete/cache.js';
export { ensureLocalCsvCacheSeeded, exportLocalTagCacheCsv, refreshLocalCsvCache, clearLocalTagCache, parseLocalTagCacheStatus } from './autocomplete/csv.js';
