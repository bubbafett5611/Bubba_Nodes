const { app } = window.comfyAPI.app;

const AUTOCOMPLETE_ENABLED_KEY = "bubba.Autocomplete.Enabled";
const AUTOCOMPLETE_SUGGESTION_LIMIT_KEY = "bubba.Autocomplete.SuggestionLimit";
const AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT = 20;

function normalizeSuggestionLimit(value) {
	const n = Number.parseInt(String(value), 10);
	if (!Number.isFinite(n)) {
		return AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT;
	}
	return Math.max(1, Math.min(100, n));
}

console.log("[Bubba] Settings.js loaded");

// Helper to create button row with consistent styling
function createButtonRow(buttons) {
	const row = document.createElement("div");
	buttons.forEach((btn, idx) => {
		if (idx > 0) btn.style.marginLeft = "8px";
		row.appendChild(btn);
	});
	return row;
}

// Helper to create styled text element
function createText(text, fontSize = "12px", opacity = 0.8, marginBottom = "6px") {
	const el = document.createElement("div");
	el.textContent = text;
	Object.assign(el.style, { fontSize, opacity, marginBottom });
	return el;
}

app.registerExtension({
	name: "bubba.core",
	async init() {
		try {
			const { BubbaTextAutoComplete, ensureLocalCsvCacheSeeded, ensureEmbeddingCacheSeeded } = await import("./autocomplete.js");
			const { installCheckpointTieredMenus } = await import("./checkpoint_menu.js");

			// installStringWidgetHook() is deferred to setup() where ComfyWidgets.STRING is ready
			BubbaTextAutoComplete.enabled = localStorage.getItem(AUTOCOMPLETE_ENABLED_KEY) !== "false";
			BubbaTextAutoComplete.suggestionLimit = normalizeSuggestionLimit(
				localStorage.getItem(AUTOCOMPLETE_SUGGESTION_LIMIT_KEY) ?? AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT,
			);
			installCheckpointTieredMenus();

			// Seed caches in background without blocking init
			try {
				await ensureLocalCsvCacheSeeded();
			} catch (err) {
				console.warn("[Bubba] Failed to seed local CSV cache:", err);
			}
			try {
				await ensureEmbeddingCacheSeeded();
			} catch (err) {
				console.warn("[Bubba] Failed to seed embedding cache:", err);
			}
		} catch (error) {
			console.error("[Bubba] Init error:", error);
		}
	},
	async setup() {
		try {
			console.log("[Bubba] Setting up...");
			const {
				BubbaTextAutoComplete,
				installStringWidgetHook,
				exportLocalTagCacheCsv,
				refreshLocalCsvCache,
				clearLocalTagCache,
				parseLocalTagCacheStatus,
			} = await import("./autocomplete.js");

			// ComfyWidgets.STRING is available by setup() time
			installStringWidgetHook();

			// Prompt Autocomplete toggle
			app.ui.settings.addSetting({
				id: AUTOCOMPLETE_ENABLED_KEY,
				name: "Bubba: Prompt Autocomplete",
				type: "boolean",
				defaultValue: true,
				onChange(value) {
					BubbaTextAutoComplete.enabled = !!value;
					localStorage.setItem(AUTOCOMPLETE_ENABLED_KEY, String(!!value));
				},
			});

			app.ui.settings.addSetting({
				id: AUTOCOMPLETE_SUGGESTION_LIMIT_KEY,
				name: "Bubba: Autocomplete Max Suggestions",
				type: "number",
				defaultValue: AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT,
				attrs: {
					min: 1,
					max: 100,
					step: 1,
				},
				onChange(value) {
					const nextLimit = normalizeSuggestionLimit(value);
					BubbaTextAutoComplete.suggestionLimit = nextLimit;
					localStorage.setItem(AUTOCOMPLETE_SUGGESTION_LIMIT_KEY, String(nextLimit));
				},
			});

			// Local CSV Cache management
			app.ui.settings.addSetting({
				id: "bubba.Autocomplete.DanbooruActions",
				name: "Bubba: Local CSV Sync + Cache",
				defaultValue: "",
				type() {
					const status = createText(parseLocalTagCacheStatus(), "12px", 0.8, "6px");
					const hint = createText(
						"Autocomplete uses an in-memory search index built from this browser cache for fast typing.",
						"12px",
						0.7,
						"6px"
					);

					const refreshBtn = document.createElement("button");
					refreshBtn.textContent = "Download Latest + Rebuild Cache";
					refreshBtn.onclick = async () => {
						await refreshLocalCsvCache(refreshBtn);
						status.textContent = parseLocalTagCacheStatus();
					};

					const clearBtn = document.createElement("button");
					clearBtn.textContent = "Clear Browser Cache";
					clearBtn.onclick = () => {
						clearLocalTagCache();
						status.textContent = parseLocalTagCacheStatus();
					};

					const exportBtn = document.createElement("button");
					exportBtn.textContent = "Export Browser Cache CSV";
					exportBtn.onclick = () => exportLocalTagCacheCsv();

					const container = document.createElement("div");
					container.appendChild(status);
					container.appendChild(hint);
					container.appendChild(createButtonRow([refreshBtn, clearBtn, exportBtn]));
					return container;
				},
			});

			// Asset Viewer
			app.ui.settings.addSetting({
				id: "bubba.AssetViewer",
				name: "Bubba: Asset Viewer",
				defaultValue: "",
				type() {
					const btn = document.createElement("button");
					btn.textContent = "Open Standalone Page";
					btn.onclick = () => {
						const url = `${window.location.origin}/extensions/bubba_nodes/comfyui/asset_viewer.html`;
						window.open(url, "_blank", "noopener,noreferrer");
					};
					const container = document.createElement("div");
					container.appendChild(btn);
					return container;
				},
			});

			console.log("[Bubba] Setup complete");
		} catch (error) {
			console.error("[Bubba] Setup error:", error);
		}
	},
});
