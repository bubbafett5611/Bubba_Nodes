const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.ViewTextNode";
const TARGET_NODE_CLASS = "BubbaViewText";
const DEFAULT_SIZE = [460, 320];
const PANEL_MARGIN = 10;
const PANEL_TOP = 42;
const LINE_HEIGHT = 16;

function normalizeText(value) {
	if (Array.isArray(value)) {
		return normalizeText(value[0]);
	}
	return String(value ?? "");
}

function wrapText(ctx, text, maxWidth) {
	const lines = [];
	for (const rawLine of String(text ?? "").split("\n")) {
		if (!rawLine) {
			lines.push("");
			continue;
		}

		let line = "";
		for (const token of rawLine.split(/(\s+)/)) {
			const nextLine = `${line}${token}`;
			if (line && ctx.measureText(nextLine).width > maxWidth) {
				lines.push(line.trimEnd());
				line = token.trimStart();
			} else {
				line = nextLine;
			}
		}
		lines.push(line);
	}
	return lines;
}

function drawText(node, ctx) {
	const text = normalizeText(node.bubbaViewText);
	const x = PANEL_MARGIN;
	const y = PANEL_TOP;
	const width = Math.max(1, node.size[0] - PANEL_MARGIN * 2);
	const height = Math.max(1, node.size[1] - PANEL_TOP - PANEL_MARGIN);

	ctx.save();
	ctx.fillStyle = "#15171c";
	ctx.fillRect(x, y, width, height);
	ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
	ctx.lineWidth = 1;
	ctx.strokeRect(x, y, width, height);

	ctx.beginPath();
	ctx.rect(x + 8, y + 8, width - 16, height - 16);
	ctx.clip();

	ctx.fillStyle = text ? "#dce3ef" : "rgba(220, 227, 239, 0.68)";
	ctx.font = "13px monospace";
	ctx.textBaseline = "top";

	const lines = text ? wrapText(ctx, text, width - 18) : ["Run the node to display text here."];
	const maxLines = Math.max(1, Math.floor((height - 16) / LINE_HEIGHT));
	const visibleLines = lines.slice(0, maxLines);
	if (lines.length > maxLines) {
		visibleLines[maxLines - 1] = "...";
	}

	for (let index = 0; index < visibleLines.length; index += 1) {
		ctx.fillText(visibleLines[index], x + 9, y + 8 + index * LINE_HEIGHT);
	}

	ctx.restore();
}

function installViewTextNode() {
	app.registerExtension({
		name: EXTENSION_NAME,
		beforeRegisterNodeDef(nodeType, nodeData) {
			if (nodeData?.name !== TARGET_NODE_CLASS) {
				return;
			}

			const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function onViewTextNodeCreated() {
				const result = typeof originalOnNodeCreated === "function"
					? originalOnNodeCreated.apply(this, arguments)
					: undefined;
				if (!this.size || this.size[0] < DEFAULT_SIZE[0] || this.size[1] < DEFAULT_SIZE[1]) {
					this.size = [...DEFAULT_SIZE];
				}
				this.bubbaViewText = "";
				return result;
			};

			const originalOnExecuted = nodeType.prototype.onExecuted;
			nodeType.prototype.onExecuted = function onViewTextNodeExecuted(output) {
				if (typeof originalOnExecuted === "function") {
					originalOnExecuted.apply(this, arguments);
				}
				this.bubbaViewText = normalizeText(output?.text);
				this.setDirtyCanvas?.(true, true);
			};

			const originalOnDrawForeground = nodeType.prototype.onDrawForeground;
			nodeType.prototype.onDrawForeground = function onViewTextNodeDrawForeground(ctx) {
				if (typeof originalOnDrawForeground === "function") {
					originalOnDrawForeground.apply(this, arguments);
				}
				drawText(this, ctx);
			};
		},
	});
}

export {
	installViewTextNode,
};
