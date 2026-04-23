const { app } = window.comfyAPI.app;
import {
	BubbaTextAutoComplete,
	installStringWidgetHook,
	ensureLocalCsvCacheSeeded,
	exportLocalTagCacheCsv,
	refreshLocalCsvCache,
	clearLocalTagCache,
	parseLocalTagCacheStatus,
} from "./autocomplete.js";
import { installCheckpointTieredMenus } from "./checkpoint_menu.js";

const AUTOCOMPLETE_EXTENSION_NAME = "bubba.prompt_autocomplete";
const ASSET_VIEWER_EXTENSION_NAME = "bubba.asset_viewer";
const AUTOCOMPLETE_ENABLED_SETTING_ID = "bubba.Autocomplete.Enabled";
const AUTOCOMPLETE_CACHE_SETTING_ID = "bubba.Autocomplete.DanbooruActions";
const ASSET_VIEWER_SETTING_ID = "bubba.Autocomplete.AssetViewer";

app.registerExtension({
	name: AUTOCOMPLETE_EXTENSION_NAME,
	init() {
		installStringWidgetHook();
		installCheckpointTieredMenus();
		BubbaTextAutoComplete.enabled = localStorage.getItem(AUTOCOMPLETE_ENABLED_SETTING_ID) !== "false";
		ensureLocalCsvCacheSeeded();
	},
	setup() {
		app.ui.settings.addSetting({
			id: AUTOCOMPLETE_ENABLED_SETTING_ID,
			name: "Bubba: Prompt Autocomplete",
			type: "boolean",
			defaultValue: true,
			onChange: (value) => {
				BubbaTextAutoComplete.enabled = !!value;
				localStorage.setItem(AUTOCOMPLETE_ENABLED_SETTING_ID, String(!!value));
			},
		});

		app.ui.settings.addSetting({
			id: AUTOCOMPLETE_CACHE_SETTING_ID,
			name: "Bubba: Local CSV Sync + Cache",
			defaultValue: "",
			type: () => {
				const status = document.createElement("div");
				status.textContent = parseLocalTagCacheStatus();
				Object.assign(status.style, { fontSize: "12px", opacity: 0.8, marginBottom: "6px" });

				const hint = document.createElement("div");
				hint.textContent = "Autocomplete uses an in-memory search index built from this browser cache for fast typing.";
				Object.assign(hint.style, { fontSize: "12px", opacity: 0.7, marginBottom: "6px" });

				const refreshButton = document.createElement("button");
				refreshButton.textContent = "Download Latest + Rebuild Cache";
				refreshButton.onclick = async () => {
					await refreshLocalCsvCache(refreshButton);
					status.textContent = parseLocalTagCacheStatus();
				};

				const clearButton = document.createElement("button");
				clearButton.textContent = "Clear Browser Cache";
				clearButton.style.marginLeft = "8px";
				clearButton.onclick = () => {
					clearLocalTagCache();
					status.textContent = parseLocalTagCacheStatus();
				};

				const exportButton = document.createElement("button");
				exportButton.textContent = "Export Browser Cache CSV";
				exportButton.style.marginLeft = "8px";
				exportButton.onclick = () => exportLocalTagCacheCsv();

				const buttonRow = document.createElement("div");
				buttonRow.append(refreshButton, clearButton, exportButton);

				const container = document.createElement("div");
				container.append(status, hint, buttonRow);
				return container;
			},
		});

	},
});

app.registerExtension({
	name: ASSET_VIEWER_EXTENSION_NAME,
	setup() {
		const openAssetViewer = () => {
			const url = `${window.location.origin}/extensions/bubba_nodes/comfyui/asset_viewer.html`;
			window.open(url, "_blank", "noopener,noreferrer");
		};

		app.ui.settings.addSetting({
			id: ASSET_VIEWER_SETTING_ID,
			name: "Bubba: Asset Viewer",
			defaultValue: "",
			type: () => {
				const btn = document.createElement("button");
				btn.textContent = "Open Standalone Page";
				btn.onclick = () => openAssetViewer();
				const container = document.createElement("div");
				container.appendChild(btn);
				return container;
			},
		});
	},
});
