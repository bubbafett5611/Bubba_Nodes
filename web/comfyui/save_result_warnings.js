const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.SaveResultWarnings";
const TARGET_NODE_CLASS = "BubbaSaveImage";
const WARNING_BADGE_HEIGHT = 28;
const WARNING_BADGE_MARGIN = 8;

function normalizeMetadataWarnings(value) {
	if (!Array.isArray(value)) {
		return [];
	}
	return value
		.flat(Infinity)
		.map((item) => String(item || "").trim())
		.filter(Boolean);
}

function formatWarningLabel(warnings) {
	const count = warnings.length;
	if (!count) {
		return "";
	}
	return count === 1 ? "Metadata warning" : `${count} metadata warnings`;
}

function formatWarningReason(warning) {
	const text = String(warning || "").toLowerCase();
	if (text.includes("contains no model")) {
		return "empty metadata";
	}
	if (text.includes("failed to embed")) {
		return "embed failed";
	}
	return String(warning || "").trim();
}

function drawWarningBadge(node, ctx, warnings) {
	const label = formatWarningLabel(warnings);
	if (!label) {
		return;
	}
	const reason = formatWarningReason(warnings[0]);

	const x = WARNING_BADGE_MARGIN;
	const y = Math.max(34, node.size[1] - WARNING_BADGE_HEIGHT - WARNING_BADGE_MARGIN);
	const width = Math.max(120, node.size[0] - WARNING_BADGE_MARGIN * 2);
	const radius = 6;

	ctx.save();
	ctx.beginPath();
	if (typeof ctx.roundRect === "function") {
		ctx.roundRect(x, y, width, WARNING_BADGE_HEIGHT, radius);
	} else {
		ctx.rect(x, y, width, WARNING_BADGE_HEIGHT);
	}
	ctx.fillStyle = "rgba(255, 176, 64, 0.22)";
	ctx.fill();
	ctx.strokeStyle = "rgba(255, 176, 64, 0.85)";
	ctx.lineWidth = 1;
	ctx.stroke();

	ctx.fillStyle = "#ffd28a";
	ctx.textBaseline = "middle";
	ctx.font = "bold 12px sans-serif";
	ctx.fillText(label, x + 10, y + WARNING_BADGE_HEIGHT / 2);
	if (reason) {
		const reasonX = x + 14 + ctx.measureText(label).width;
		const maxReasonWidth = Math.max(0, x + width - reasonX - 10);
		ctx.font = "12px sans-serif";
		ctx.fillStyle = "rgba(255, 230, 190, 0.88)";
		ctx.fillText(`- ${reason}`, reasonX, y + WARNING_BADGE_HEIGHT / 2, maxReasonWidth);
	}
	ctx.restore();
}

function showMetadataWarningToast(warnings) {
	if (!warnings.length) {
		return;
	}
	const message = `${formatWarningLabel(warnings)}: ${warnings[0]}`;
	if (app.extensionManager?.toast?.add) {
		app.extensionManager.toast.add({
			severity: "warn",
			summary: "Bubba Save Image",
			detail: message,
			life: 6000,
		});
		return;
	}
	console.warn(`[Bubba] ${message}`);
}

function installSaveResultWarnings() {
	app.registerExtension({
		name: EXTENSION_NAME,
		beforeRegisterNodeDef(nodeType, nodeData) {
			if (nodeData?.name !== TARGET_NODE_CLASS) {
				return;
			}

			const originalOnExecuted = nodeType.prototype.onExecuted;
			nodeType.prototype.onExecuted = function onExecutedWithMetadataWarnings(output) {
				if (typeof originalOnExecuted === "function") {
					originalOnExecuted.apply(this, arguments);
				}

				const warnings = normalizeMetadataWarnings(output?.metadata_warnings);
				this.bubbaMetadataWarnings = warnings;
				if (warnings.length) {
					showMetadataWarningToast(warnings);
				}
				this.setDirtyCanvas?.(true, true);
			};

			const originalOnDrawForeground = nodeType.prototype.onDrawForeground;
			nodeType.prototype.onDrawForeground = function onDrawForegroundWithMetadataWarnings(ctx) {
				if (typeof originalOnDrawForeground === "function") {
					originalOnDrawForeground.apply(this, arguments);
				}
				drawWarningBadge(this, ctx, this.bubbaMetadataWarnings || []);
			};
		},
	});
}

export {
	installSaveResultWarnings,
};
