import { app } from "../../../scripts/app.js";
import { $el } from "../../../scripts/ui.js";
import {
	id,
	BubbaTextAutoComplete,
	installStringWidgetHook,
	ensureDanbooruCacheSeeded,
	isDanbooruEnabled,
	danbooruEnabledStorageKey,
	debugStorageKey,
	openCustomWordsEditor,
	downloadDanbooruCacheFile,
	refreshDanbooruTagsFromPrompts,
	clearDanbooruTagCache,
	parseStatusFromMeta,
} from "./autocomplete.js";

app.registerExtension({
	name: id,
	init() {
		installStringWidgetHook();
		BubbaTextAutoComplete.enabled = localStorage.getItem(`${id}.Enabled`) !== "false";
		ensureDanbooruCacheSeeded();
	},
	setup() {
		const openAssetViewer = () => {
			const url = `${window.location.origin}/extensions/bubba_nodes/comfyui/asset_viewer.html`;
			window.open(url, "_blank", "noopener,noreferrer");
		};

		app.ui.settings.addSetting({
			id: `${id}.Enabled`,
			name: "Bubba: Prompt Autocomplete",
			type: "boolean",
			defaultValue: true,
			onChange: (value) => {
				BubbaTextAutoComplete.enabled = !!value;
				localStorage.setItem(`${id}.Enabled`, String(!!value));
			},
		});

		app.ui.settings.addSetting({
			id: `${id}.CustomWords`,
			name: "Bubba: Edit Autocomplete Words",
			defaultValue: "",
			type: () =>
				$el("tr", [
					$el("td", [
						$el("label", {
							textContent: "Bubba: Edit Autocomplete Words",
						}),
					]),
					$el("td", [
						$el("button", {
							textContent: "Open File",
							onclick: () => openCustomWordsEditor(),
						}),
					]),
				]),
		});

		app.ui.settings.addSetting({
			id: `${id}.UseDanbooru`,
			name: "Bubba: Include Danbooru Tags",
			type: "boolean",
			defaultValue: isDanbooruEnabled(),
			onChange: (value) => {
				localStorage.setItem(danbooruEnabledStorageKey, String(!!value));
			},
		});

		app.ui.settings.addSetting({
			id: `${id}.Debug`,
			name: "Bubba: Debug Fetch Logs",
			type: "boolean",
			defaultValue: localStorage.getItem(debugStorageKey) === "true",
			onChange: (value) => {
				localStorage.setItem(debugStorageKey, String(!!value));
			},
		});

		app.ui.settings.addSetting({
			id: `${id}.DanbooruActions`,
			name: "Bubba: Danbooru Tag Cache",
			defaultValue: "",
			type: () => {
				const status = $el("div", {
					textContent: parseStatusFromMeta(),
					style: {
						fontSize: "12px",
						opacity: 0.8,
						marginBottom: "6px",
					},
				});
				const refreshButton = $el("button", {
					textContent: "Refresh from Danbooru",
					onclick: async () => {
						await refreshDanbooruTagsFromPrompts(refreshButton, false);
						status.textContent = parseStatusFromMeta();
					},
				});
				const fullSyncButton = $el("button", {
					textContent: "Full Sync (All >= Min Count)",
					style: {
						marginLeft: "8px",
					},
					onclick: async () => {
						await refreshDanbooruTagsFromPrompts(fullSyncButton, true);
						status.textContent = parseStatusFromMeta();
					},
				});
				const clearButton = $el("button", {
					textContent: "Clear Cache",
					style: {
						marginLeft: "8px",
					},
					onclick: () => {
						clearDanbooruTagCache();
						status.textContent = parseStatusFromMeta();
					},
				});
				const exportButton = $el("button", {
					textContent: "Export Cache CSV",
					style: {
						marginLeft: "8px",
					},
					onclick: () => {
						downloadDanbooruCacheFile();
					},
				});

				return $el("tr", [
					$el("td", [
						$el("label", {
							textContent: "Bubba: Danbooru Tag Cache",
						}),
					]),
					$el("td", [
						status,
						$el("div", [refreshButton, fullSyncButton, clearButton, exportButton]),
					]),
				]);
			},
		});

		app.ui.settings.addSetting({
			id: `${id}.AssetViewer`,
			name: "Bubba: Asset Viewer",
			defaultValue: "",
			type: () =>
				$el("tr", [
					$el("td", [
						$el("label", {
							textContent: "Bubba: Asset Viewer",
						}),
					]),
					$el("td", [
						$el("button", {
							textContent: "Open Standalone Page",
							onclick: () => openAssetViewer(),
						}),
					]),
				]),
		});
	},
});
