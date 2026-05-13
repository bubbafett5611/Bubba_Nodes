const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.ImageCompareNode";
const TARGET_NODE_CLASS = "BubbaImageCompare";

function clamp01(value) {
    const n = Number.parseFloat(String(value));
    if (!Number.isFinite(n)) {
        return 0.5;
    }
    return Math.max(0, Math.min(1, n));
}

function fitContain(srcW, srcH, maxW, maxH) {
    if (!srcW || !srcH || !maxW || !maxH) {
        return { x: 0, y: 0, w: 0, h: 0 };
    }
    const s = Math.min(maxW / srcW, maxH / srcH);
    const w = Math.max(1, Math.floor(srcW * s));
    const h = Math.max(1, Math.floor(srcH * s));
    const x = Math.floor((maxW - w) / 2);
    const y = Math.floor((maxH - h) / 2);
    return { x, y, w, h };
}

function installImageCompareNode() {
    app.registerExtension({
        name: EXTENSION_NAME,
        beforeRegisterNodeDef(nodeType, nodeData) {
            if (nodeData?.name !== TARGET_NODE_CLASS) {
                return;
            }

            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function onImageCompareNodeCreated() {
                const out = typeof originalOnNodeCreated === "function"
                    ? originalOnNodeCreated.apply(this, arguments)
                    : undefined;

                if (!this.size || this.size[0] < 100 || this.size[1] < 100) {
                    this.size = [560, 620];
                }

                this.sliderPos = 0.5;
                this.dragging = false;
                this.hovered = false;
                this.imgA = null;
                this.imgB = null;

                const getDrawGeom = () => {
                    const margin = 10;
                    const topOffset = 40;
                    const drawX = margin;
                    const drawY = margin + topOffset;
                    const drawW = Math.max(1, this.size[0] - margin * 2);
                    const drawH = Math.max(1, (this.size[1] - margin * 2) - topOffset);
                    return { drawX, drawY, drawW, drawH };
                };

                this.onMouseDown = function onMouseDown(_, pos) {
                    const { drawX, drawY, drawW, drawH } = getDrawGeom();
                    const x = pos[0] - drawX;
                    const y = pos[1] - drawY;

                    if (x < 0 || x > drawW || y < 0 || y > drawH) {
                        return false;
                    }

                    this.dragging = true;
                    this.sliderPos = clamp01(x / drawW);
                    this.setDirtyCanvas?.(true, true);
                    return true;
                };

                this.onMouseMove = function onMouseMove(e, pos) {
                    const { drawX, drawY, drawW, drawH } = getDrawGeom();
                    const splitX = drawX + Math.floor(drawW * this.sliderPos);
                    const handleY = drawY + Math.floor(drawH / 2);
                    const dist = Math.hypot(pos[0] - splitX, pos[1] - handleY);
                    this.hovered = dist < 16;

                    if (this.dragging && e && e.buttons !== undefined && e.buttons === 0) {
                        this.dragging = false;
                    }

                    if (this.dragging) {
                        let x = pos[0] - drawX;
                        x = Math.max(0, Math.min(drawW, x));
                        const newPos = clamp01(x / drawW);
                        if (Math.abs(newPos - this.sliderPos) > 0.001) {
                            this.sliderPos = newPos;
                            this.setDirtyCanvas?.(true, true);
                        }
                    }
                };

                this.onMouseUp = function onMouseUp() {
                    this.dragging = false;
                    return false;
                };

                this.onDrawForeground = function onDrawForeground(ctx) {
                    ctx.save();
                    const { drawX, drawY, drawW, drawH } = getDrawGeom();

                    ctx.fillStyle = "#101216";
                    ctx.fillRect(drawX, drawY, drawW, drawH);

                    if (!this.imgA || !this.imgB) {
                        ctx.fillStyle = "#c4ccd9";
                        ctx.font = "13px sans-serif";
                        ctx.fillText("Run the node to preview draggable A/B compare", drawX + 12, drawY + 24);
                        ctx.restore();
                        return;
                    }

                    const rectA = fitContain(this.imgA.width, this.imgA.height, drawW, drawH);
                    const rectB = fitContain(this.imgB.width, this.imgB.height, drawW, drawH);

                    ctx.drawImage(this.imgB, drawX + rectB.x, drawY + rectB.y, rectB.w, rectB.h);

                    const splitX = drawX + Math.floor(drawW * this.sliderPos);
                    ctx.save();
                    ctx.beginPath();
                    ctx.rect(drawX, drawY, splitX - drawX, drawH);
                    ctx.clip();
                    ctx.drawImage(this.imgA, drawX + rectA.x, drawY + rectA.y, rectA.w, rectA.h);
                    ctx.restore();

                    ctx.strokeStyle = "#00e0ff";
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(splitX, drawY);
                    ctx.lineTo(splitX, drawY + drawH);
                    ctx.stroke();

                    if (this.hovered || this.dragging) {
                        ctx.fillStyle = "#00e0ff";
                        ctx.beginPath();
                        ctx.arc(splitX, drawY + Math.floor(drawH / 2), 6, 0, Math.PI * 2);
                        ctx.fill();
                    }

                    ctx.fillStyle = "#ffffff";
                    ctx.shadowColor = "#000000";
                    ctx.shadowOffsetX = 1;
                    ctx.shadowOffsetY = 1;
                    ctx.font = "bold 14px sans-serif";
                    ctx.fillText("A", drawX + 8, drawY + 20);
                    ctx.fillText("B", drawX + drawW - 18, drawY + 20);

                    ctx.restore();
                };

                const originalOnExecuted = this.onExecuted;
                this.onExecuted = function onExecutedWithPreview(output) {
                    if (typeof originalOnExecuted === "function") {
                        originalOnExecuted.apply(this, arguments);
                    }

                    if (!output?.b64_a || !output?.b64_b) {
                        return;
                    }

                    const aData = Array.isArray(output.b64_a) ? output.b64_a.join("") : output.b64_a;
                    const bData = Array.isArray(output.b64_b) ? output.b64_b.join("") : output.b64_b;

                    if (!aData || !bData) {
                        return;
                    }

                    this.imgA = new Image();
                    this.imgB = new Image();
                    this.imgA.onload = () => this.setDirtyCanvas?.(true, true);
                    this.imgB.onload = () => this.setDirtyCanvas?.(true, true);
                    this.imgA.onerror = () => console.warn("[Bubba] Image Compare: failed to load image A");
                    this.imgB.onerror = () => console.warn("[Bubba] Image Compare: failed to load image B");
                    this.imgA.src = `data:image/png;base64,${aData}`;
                    this.imgB.src = `data:image/png;base64,${bData}`;
                };

                return out;
            };
        },
    });
}

export {
    installImageCompareNode,
};
