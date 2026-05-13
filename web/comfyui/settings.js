const { app } = window.comfyAPI.app;
import { CIVITAI_DOMAIN_KEEP, CIVITAI_DOMAIN_KEY } from "./menu_shared.js";

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
const CIVITAI_DOMAIN_OPTIONS = [
	{ value: CIVITAI_DOMAIN_KEEP, label: "Keep original URL" },
	{ value: "civitai.com", label: "civitai.com" },
	{ value: "civitai.red", label: "civitai.red" },
	{ value: "civitai.green", label: "civitai.green" },
];

function normalizeSuggestionLimit(value) {
	const n = Number.parseInt(String(value), 10);
	if (!Number.isFinite(n)) {
		return AUTOCOMPLETE_SUGGESTION_LIMIT_DEFAULT;
	}
	return Math.max(1, Math.min(100, n));
}

console.log("[Bubba] Settings.js loaded");

function createSettingPanel() {
	const panel = document.createElement("div");
	Object.assign(panel.style, {
		display: "flex",
		flexDirection: "column",
		gap: "8px",
		maxWidth: "720px",
		padding: "8px 0",
	});
	return panel;
}

function styleSettingButton(button) {
	Object.assign(button.style, {
		minHeight: "30px",
		padding: "0 12px",
		borderRadius: "8px",
		whiteSpace: "nowrap",
	});
	return button;
}

function styleSettingSelect(select) {
	Object.assign(select.style, {
		minHeight: "34px",
		minWidth: "220px",
		maxWidth: "320px",
		padding: "0 10px",
		borderRadius: "8px",
	});
	return select;
}

function styleSettingInput(input) {
	Object.assign(input.style, {
		minHeight: "34px",
		padding: "0 10px",
		borderRadius: "8px",
		maxWidth: "320px",
	});
	return input;
}

function styleSettingTextarea(textarea) {
	Object.assign(textarea.style, {
		minHeight: "96px",
		width: "100%",
		maxWidth: "720px",
		padding: "8px 10px",
		borderRadius: "8px",
		resize: "vertical",
		boxSizing: "border-box",
	});
	return textarea;
}

function createStatusText(text) {
	const el = document.createElement("div");
	el.textContent = text;
	Object.assign(el.style, {
		fontSize: "12px",
		lineHeight: "1.45",
		opacity: "0.92",
	});
	return el;
}

function createFieldRow() {
	const row = document.createElement("div");
	Object.assign(row.style, {
		display: "flex",
		flexWrap: "wrap",
		alignItems: "center",
		gap: "8px",
	});
	return row;
}

// Helper to create button row with consistent styling
function createButtonRow(buttons) {
	const row = document.createElement("div");
	Object.assign(row.style, {
		display: "flex",
		flexWrap: "wrap",
		alignItems: "center",
		gap: "8px",
	});
	buttons.forEach((btn) => {
		styleSettingButton(btn);
		row.appendChild(btn);
	});
	return row;
}

// Helper to create styled text element
function createText(text, fontSize = "12px", opacity = 0.8, marginBottom = "6px") {
	const el = document.createElement("div");
	el.textContent = text;
	Object.assign(el.style, {
		fontSize,
		lineHeight: "1.45",
		opacity,
		marginBottom,
	});
	return el;
}

function getStoredCivitaiDomain() {
	const current = String(localStorage.getItem(CIVITAI_DOMAIN_KEY) || CIVITAI_DOMAIN_KEEP);
	return CIVITAI_DOMAIN_OPTIONS.some((option) => option.value === current) ? current : CIVITAI_DOMAIN_KEEP;
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
				readPromptSnippets,
				savePromptSnippet,
				deletePromptSnippet,
				normalizeSnippetName,
				exportPromptSnippetsJson,
				importPromptSnippetsJson,
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
				id: CIVITAI_DOMAIN_KEY,
				name: "Bubba: CivitAI Link Domain",
				defaultValue: CIVITAI_DOMAIN_KEEP,
				type() {
					const container = createSettingPanel();
					const hint = createText(
						"Choose which CivitAI domain Bubba uses when opening model links from menu entries.",
						"12px",
						0.7,
						"0",
					);
					const select = document.createElement("select");
					for (const option of CIVITAI_DOMAIN_OPTIONS) {
						const element = document.createElement("option");
						element.value = option.value;
						element.textContent = option.label;
						select.appendChild(element);
					}
					styleSettingSelect(select);
					select.value = getStoredCivitaiDomain();
					select.onchange = () => {
						localStorage.setItem(CIVITAI_DOMAIN_KEY, String(select.value || CIVITAI_DOMAIN_KEEP));
					};
					container.appendChild(hint);
					container.appendChild(select);
					return container;
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
					const container = createSettingPanel();
					const status = createStatusText(parseLocalTagCacheStatus());
					const hint = createText(
						"Autocomplete uses an in-memory search index built from local source CSVs and this browser cache for fast typing.",
						"12px",
						0.7,
						"0",
					);

					const refreshBtn = document.createElement("button");
					refreshBtn.textContent = "Download Sources + Rebuild Cache";
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

					container.appendChild(status);
					container.appendChild(hint);
					container.appendChild(createButtonRow([refreshBtn, clearBtn, exportBtn]));
					return container;
				},
			});

			app.ui.settings.addSetting({
				id: "bubba.PromptSnippets.Manager",
				name: "Bubba: Prompt Snippets",
				defaultValue: "",
				type() {
					const container = createSettingPanel();
					const hint = createText(
						"Save reusable prompt blocks here, then type @snippet_name in any Bubba multiline prompt to expand them inline.",
						"12px",
						0.7,
						"0",
					);
					const status = createText("", "12px", 0.85, "0");
					const fieldsRow = createFieldRow();
					const nameInput = styleSettingInput(document.createElement("input"));
					nameInput.type = "text";
					nameInput.placeholder = "snippet_name";
					const categoryInput = styleSettingInput(document.createElement("input"));
					categoryInput.type = "text";
					categoryInput.placeholder = "category (optional)";
					fieldsRow.appendChild(nameInput);
					fieldsRow.appendChild(categoryInput);

					const textInput = styleSettingTextarea(document.createElement("textarea"));
					textInput.placeholder = "Snippet text inserted when you choose @snippet_name from autocomplete.";
					const importInput = document.createElement("input");
					importInput.type = "file";
					importInput.accept = "application/json,.json";
					importInput.hidden = true;

					const list = document.createElement("div");
					Object.assign(list.style, {
						display: "flex",
						flexDirection: "column",
						gap: "8px",
						marginTop: "4px",
					});

					let editingName = "";

					const setStatus = (message, isError = false) => {
						status.textContent = message;
						status.style.color = isError ? "var(--error-text, #ff9b9b)" : "";
					};

					const resetForm = () => {
						editingName = "";
						nameInput.value = "";
						categoryInput.value = "";
						textInput.value = "";
						setStatus("");
					};

					const renderSnippetList = () => {
						list.replaceChildren();
						const snippets = readPromptSnippets();
						if (!snippets.length) {
							list.appendChild(createText("No snippets yet. Add one here, then trigger it with @name in a prompt.", "12px", 0.7, "0"));
							return;
						}

						for (const snippet of snippets) {
							const card = document.createElement("div");
							Object.assign(card.style, {
								display: "flex",
								flexDirection: "column",
								gap: "6px",
								padding: "10px 12px",
								borderRadius: "8px",
								border: "1px solid rgba(128, 128, 128, 0.28)",
								background: "rgba(128, 128, 128, 0.08)",
								maxWidth: "720px",
							});

							const topRow = createFieldRow();
							Object.assign(topRow.style, {
								justifyContent: "space-between",
							});

							const title = document.createElement("div");
							title.textContent = `@${snippet.name}${snippet.category ? ` - ${snippet.category}` : ""}`;
							Object.assign(title.style, {
								fontSize: "12px",
								fontWeight: "600",
							});

							const actions = createButtonRow([
								Object.assign(document.createElement("button"), {
									textContent: "Edit",
									onclick: () => {
										editingName = snippet.name;
										nameInput.value = snippet.name;
										categoryInput.value = snippet.category || "";
										textInput.value = snippet.text;
										setStatus(`Editing @${snippet.name}`);
									},
								}),
								Object.assign(document.createElement("button"), {
									textContent: "Delete",
									onclick: () => {
										deletePromptSnippet(snippet.name);
										if (editingName === snippet.name) {
											resetForm();
										}
										renderSnippetList();
									},
								}),
							]);
							Object.assign(actions.style, {
								marginLeft: "auto",
							});

							topRow.appendChild(title);
							topRow.appendChild(actions);
							card.appendChild(topRow);

							const preview = createText(snippet.text, "12px", 0.82, "0");
							Object.assign(preview.style, {
								whiteSpace: "pre-wrap",
								wordBreak: "break-word",
							});
							card.appendChild(preview);
							list.appendChild(card);
						}
					};

					const saveButton = document.createElement("button");
					saveButton.textContent = "Save Snippet";
					saveButton.onclick = () => {
						const nextName = normalizeSnippetName(nameInput.value);
						const nextText = String(textInput.value || "").trim();
						if (!nextName) {
							setStatus("Snippet name is required.", true);
							return;
						}
						if (!nextText) {
							setStatus("Snippet text is required.", true);
							return;
						}
						try {
							const saved = savePromptSnippet({
								name: nextName,
								category: categoryInput.value,
								text: nextText,
							}, editingName);
							renderSnippetList();
							editingName = saved.name;
							nameInput.value = saved.name;
							setStatus(`Saved @${saved.name}`);
						} catch {
							setStatus("Could not save snippet.", true);
						}
					};

					const resetButton = document.createElement("button");
					resetButton.textContent = "New Snippet";
					resetButton.onclick = () => resetForm();

					const exportButton = document.createElement("button");
					exportButton.textContent = "Export JSON";
					exportButton.onclick = () => {
						try {
							const blob = new Blob([exportPromptSnippetsJson()], { type: "application/json" });
							const url = URL.createObjectURL(blob);
							const link = document.createElement("a");
							link.href = url;
							link.download = "bubba-prompt-snippets.json";
							link.click();
							URL.revokeObjectURL(url);
							setStatus(`Exported ${readPromptSnippets().length} snippet${readPromptSnippets().length === 1 ? "" : "s"}.`);
						} catch {
							setStatus("Could not export snippets.", true);
						}
					};

					const importButton = document.createElement("button");
					importButton.textContent = "Import JSON";
					importButton.onclick = () => {
						importInput.value = "";
						importInput.click();
					};

					importInput.onchange = async () => {
						const file = importInput.files?.[0];
						if (!file) {
							return;
						}
						try {
							const raw = await file.text();
							const imported = importPromptSnippetsJson(raw, { mode: "merge" });
							renderSnippetList();
							setStatus(`Imported ${imported.length} total snippet${imported.length === 1 ? "" : "s"} after merge.`);
						} catch {
							setStatus("Could not import snippets from that file.", true);
						}
					};

					container.appendChild(hint);
					container.appendChild(fieldsRow);
					container.appendChild(textInput);
					container.appendChild(createButtonRow([saveButton, resetButton, exportButton, importButton]));
					container.appendChild(importInput);
					container.appendChild(status);
					container.appendChild(list);
					renderSnippetList();
					return container;
				},
			});
			console.log("[Bubba] Setup complete");
		} catch (error) {
			console.error("[Bubba] Setup error:", error);
		}
	},
});
