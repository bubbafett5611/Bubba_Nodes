const { app } = window.comfyAPI.app;

const AUTOCOMPLETE_ENABLED_KEY = "bubba.Autocomplete.Enabled";
const PROMPT_ASSISTANT_ENABLED_KEY = "bubba.PromptAssistant.Enabled";
const AUTOCOMPLETE_SUGGESTION_LIMIT_KEY = "bubba.Autocomplete.SuggestionLimit";
const AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT = 20;
const AUTOCOMPLETE_REPLACE_UNDERSCORES_KEY = "bubba.Autocomplete.ReplaceUnderscores";
const MANUAL_SEED_AUTO_QUEUE_KEY = "bubba.KSampler.ManualSeed.AutoQueue";
const CHECKPOINT_PREVIEW_ENABLED_KEY = "bubba.CheckpointPreview.Enabled";
const CHECKPOINT_MENU_DENSE_KEY = "bubba.CheckpointMenu.Dense";
const CHECKPOINT_MENU_FONT_SCALE_KEY = "bubba.CheckpointMenu.FontScale";
const CHECKPOINT_MENU_CONTRAST_KEY = "bubba.CheckpointMenu.Contrast";
const CHECKPOINT_MENU_ICON_SCALE_KEY = "bubba.CheckpointMenu.IconScale";
const CHECKPOINT_MENU_RECENTS_LIMIT_KEY = "bubba.CheckpointMenu.RecentsLimit";

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
			const { installLoraTieredMenus } = await import("./lora_menu.js");
			const { installEmptyLatentSizeMenu } = await import("./latent_size_menu.js");
			const { installSamplerSeedButton } = await import("./sampler_seed_button.js");
			const { installImageCompareNode } = await import("./image_compare_node.js");
			const { installSaveResultWarnings } = await import("./save_result_warnings.js");
			const { installMetadataDebugNode } = await import("./metadata_debug_node.js");

			// installStringWidgetHook() is deferred to setup() where ComfyWidgets.STRING is ready
			BubbaTextAutoComplete.enabled = localStorage.getItem(AUTOCOMPLETE_ENABLED_KEY) !== "false";
			BubbaTextAutoComplete.promptAssistantEnabled = localStorage.getItem(PROMPT_ASSISTANT_ENABLED_KEY) !== "false";
			BubbaTextAutoComplete.suggestionLimit = normalizeSuggestionLimit(
				localStorage.getItem(AUTOCOMPLETE_SUGGESTION_LIMIT_KEY) ?? AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT,
			);
			BubbaTextAutoComplete.replaceUnderscores = localStorage.getItem(AUTOCOMPLETE_REPLACE_UNDERSCORES_KEY) === "true";
			installCheckpointTieredMenus();
			installLoraTieredMenus();
			installEmptyLatentSizeMenu();
			installSamplerSeedButton();
			installImageCompareNode();
			installSaveResultWarnings();
			installMetadataDebugNode();

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
				id: PROMPT_ASSISTANT_ENABLED_KEY,
				name: "Bubba: Prompt Tag Chips + Hints",
				type: "boolean",
				defaultValue: true,
				onChange(value) {
					BubbaTextAutoComplete.promptAssistantEnabled = !!value;
					localStorage.setItem(PROMPT_ASSISTANT_ENABLED_KEY, String(!!value));
				},
			});

			app.ui.settings.addSetting({
				id: MANUAL_SEED_AUTO_QUEUE_KEY,
				name: "Bubba: Manual Random Seed Auto-Run",
				type: "boolean",
				defaultValue: true,
				onChange(value) {
					localStorage.setItem(MANUAL_SEED_AUTO_QUEUE_KEY, String(!!value));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_PREVIEW_ENABLED_KEY,
				name: "Bubba: Checkpoint Hover Preview",
				type: "boolean",
				defaultValue: true,
				onChange(value) {
					localStorage.setItem(CHECKPOINT_PREVIEW_ENABLED_KEY, String(!!value));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_MENU_DENSE_KEY,
				name: "Bubba: Checkpoint Menu Dense Rows",
				type: "boolean",
				defaultValue: false,
				onChange(value) {
					localStorage.setItem(CHECKPOINT_MENU_DENSE_KEY, String(!!value));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_MENU_FONT_SCALE_KEY,
				name: "Bubba: Checkpoint Menu Font Scale",
				type: "number",
				defaultValue: 1,
				attrs: {
					min: 0.8,
					max: 1.4,
					step: 0.05,
				},
				onChange(value) {
					const n = Number.parseFloat(String(value));
					const next = Number.isFinite(n) ? Math.max(0.8, Math.min(1.4, n)) : 1;
					localStorage.setItem(CHECKPOINT_MENU_FONT_SCALE_KEY, String(next));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_MENU_CONTRAST_KEY,
				name: "Bubba: Checkpoint Menu Contrast",
				type: "number",
				defaultValue: 1,
				attrs: {
					min: 0.8,
					max: 1.5,
					step: 0.05,
				},
				onChange(value) {
					const n = Number.parseFloat(String(value));
					const next = Number.isFinite(n) ? Math.max(0.8, Math.min(1.5, n)) : 1;
					localStorage.setItem(CHECKPOINT_MENU_CONTRAST_KEY, String(next));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_MENU_ICON_SCALE_KEY,
				name: "Bubba: Checkpoint Menu Icon Scale",
				type: "number",
				defaultValue: 1,
				attrs: {
					min: 0.8,
					max: 1.6,
					step: 0.05,
				},
				onChange(value) {
					const n = Number.parseFloat(String(value));
					const next = Number.isFinite(n) ? Math.max(0.8, Math.min(1.6, n)) : 1;
					localStorage.setItem(CHECKPOINT_MENU_ICON_SCALE_KEY, String(next));
				},
			});

			app.ui.settings.addSetting({
				id: CHECKPOINT_MENU_RECENTS_LIMIT_KEY,
				name: "Bubba: Checkpoint Menu Max Recents",
				type: "number",
				defaultValue: 14,
				attrs: {
					min: 0,
					max: 50,
					step: 1,
				},
				onChange(value) {
					const n = Number.parseInt(String(value), 10);
					const next = Number.isFinite(n) ? Math.max(0, Math.min(50, n)) : 14;
					localStorage.setItem(CHECKPOINT_MENU_RECENTS_LIMIT_KEY, String(next));
				},
			});

			app.ui.settings.addSetting({
				id: AUTOCOMPLETE_REPLACE_UNDERSCORES_KEY,
				name: "Bubba: Autocomplete Replace Underscores with Spaces",
				type: "boolean",
				defaultValue: false,
				onChange(value) {
					BubbaTextAutoComplete.replaceUnderscores = !!value;
					localStorage.setItem(AUTOCOMPLETE_REPLACE_UNDERSCORES_KEY, String(!!value));
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
			console.log("[Bubba] Setup complete");
		} catch (error) {
			console.error("[Bubba] Setup error:", error);
		}
	},
});
