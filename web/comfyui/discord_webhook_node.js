const { app } = window.comfyAPI.app;

const TARGET_NODE_CLASS = "BubbaDiscordWebhook";

function showToast(severity, summary, detail) {
	if (app.extensionManager?.toast?.add) {
		app.extensionManager.toast.add({ severity, summary, detail, life: 6000 });
		return;
	}
	console[severity === "error" ? "error" : "log"](`[Bubba] ${summary}: ${detail}`);
}

async function postJson(path, payload) {
	const response = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
	});
	const result = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(result.error || `Request failed with HTTP ${response.status}`);
	}
	return result;
}

function installDiscordWebhookNode() {
	app.registerExtension({
		name: "bubba.DiscordWebhookNode",
		beforeRegisterNodeDef(nodeType, nodeData) {
			if (nodeData?.name !== TARGET_NODE_CLASS) {
				return;
			}

			const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function onDiscordNodeCreated() {
				if (typeof originalOnNodeCreated === "function") {
					originalOnNodeCreated.apply(this, arguments);
				}

				this.addWidget("button", "Send Latest Now", null, async () => {
					const button = this.widgets?.find((widget) => widget.name === "Send Latest Now");
					if (button) button.disabled = true;
					try {
						const result = await postJson("/bubba/discord/send-staged", { staging_id: String(this.id) });
						showToast("success", "Discord webhook", `Sent ${result.image_count} image(s) in ${result.message_count} message(s).`);
					} catch (error) {
						showToast("error", "Discord webhook", error.message || String(error));
					} finally {
						if (button) button.disabled = false;
					}
				});

				this.addWidget("button", "Clear Captured Images", null, async () => {
					try {
						const result = await postJson("/bubba/discord/clear-staged", { staging_id: String(this.id) });
						showToast("info", "Discord webhook", result.status === "cleared" ? "Captured images cleared." : "Nothing was captured.");
					} catch (error) {
						showToast("error", "Discord webhook", error.message || String(error));
					}
				});
			};

			const originalOnExecuted = nodeType.prototype.onExecuted;
			nodeType.prototype.onExecuted = function onDiscordExecuted(output) {
				if (typeof originalOnExecuted === "function") {
					originalOnExecuted.apply(this, arguments);
				}
				const status = Array.isArray(output?.discord_status) ? output.discord_status[0] : output?.discord_status;
				const info = Array.isArray(output?.discord_info) ? output.discord_info[0] : output?.discord_info;
				if (status === "error") {
					showToast("error", "Discord webhook", info || "Send failed.");
				} else if (status === "sent") {
					showToast("success", "Discord webhook", info || "Images sent.");
				} else if (status === "staged") {
					showToast("info", "Discord webhook", info || "Latest images captured.");
				}
			};
		},
	});
}

export { installDiscordWebhookNode };
