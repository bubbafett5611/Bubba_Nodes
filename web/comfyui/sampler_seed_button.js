const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.SamplerSeedButton";
const TARGET_NODE_CLASS = "BubbaKSampler";
const SEED_WIDGET_NAME = "seed";
const BUTTON_LABEL = "Manual Random Seed";
const AUTO_QUEUE_KEY = "bubba.KSampler.ManualSeed.AutoQueue";
const FIXED_CONTROL_VALUE = "fixed";
const MANUAL_SEED_MAX = 1125899906842624; // EasyUse-style 2^50 cap.

function toFiniteNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function getSeedWidgetBounds(seedWidget) {
    const options = seedWidget?.options ?? {};
    const min = Math.floor(Math.max(0, toFiniteNumber(options.min, 0)));
    const max = Math.floor(Math.min(MANUAL_SEED_MAX, toFiniteNumber(options.max, MANUAL_SEED_MAX)));
    if (max < min) {
        return { min: 0, max: MANUAL_SEED_MAX };
    }
    return { min, max };
}

function randomIntInRange(min, max) {
    const span = (max - min) + 1;
    if (span <= 1) {
        return min;
    }

    if (globalThis.crypto?.getRandomValues) {
        const parts = new Uint32Array(2);
        globalThis.crypto.getRandomValues(parts);
        const value = (BigInt(parts[0]) << 32n) | BigInt(parts[1]);
        return min + Number(value % BigInt(span));
    }

    return min + Math.floor(Math.random() * span);
}

function setWidgetValue(widget, value, node) {
    if (!widget || typeof widget !== "object") {
        return false;
    }

    if (typeof widget.setValue === "function") {
        try {
            widget.setValue(value);
            return true;
        } catch {
            // Fallback for frontend compatibility.
        }
    }

    try {
        widget.value = value;
    } catch {
        return false;
    }

    if (typeof widget.callback === "function") {
        try {
            widget.callback(value, app, node);
        } catch {
            try {
                widget.callback(value, app);
            } catch {
                // Ignore callback signature differences.
            }
        }
    }

    return true;
}

function setSeedControlFixed(node, seedWidget) {
    const controlNames = new Set(["control_before_generate", "control_after_generate", "seed_control"]);

    const directControls = Array.isArray(node?.widgets)
        ? node.widgets.filter((widget) => controlNames.has(widget?.name))
        : [];

    if (directControls.length > 0) {
        for (const control of directControls) {
            if (String(control.value) !== FIXED_CONTROL_VALUE) {
                setWidgetValue(control, FIXED_CONTROL_VALUE, node);
            }
        }
        return;
    }

    const linked = Array.isArray(seedWidget?.linkedWidgets) ? seedWidget.linkedWidgets : [];
    for (const entry of linked) {
        const control = entry?.widget ?? entry;
        if (controlNames.has(control?.name) && String(control.value) !== FIXED_CONTROL_VALUE) {
            setWidgetValue(control, FIXED_CONTROL_VALUE, node);
        }
    }
}

function setSeedValue(node, seed) {
    const seedWidget = node?.widgets?.find((widget) => widget?.name === SEED_WIDGET_NAME);
    if (!seedWidget) {
        return false;
    }

    const { min, max } = getSeedWidgetBounds(seedWidget);
    const clampedSeed = Math.max(min, Math.min(max, Math.floor(toFiniteNumber(seed, min))));

    setSeedControlFixed(node, seedWidget);
    const applied = setWidgetValue(seedWidget, clampedSeed, node);

    if (typeof node.setDirtyCanvas === "function") {
        node.setDirtyCanvas(true, true);
    }
    if (typeof app?.graph?.setDirtyCanvas === "function") {
        app.graph.setDirtyCanvas(true, true);
    }

    return applied;
}

function shouldAutoQueueAfterManualSeed() {
    const raw = localStorage.getItem(AUTO_QUEUE_KEY);
    return raw === null ? true : raw !== "false";
}

async function queueWorkflowIfEnabled() {
    if (!shouldAutoQueueAfterManualSeed()) {
        return;
    }

    if (typeof app?.queuePrompt === "function") {
        try {
            await app.queuePrompt(0);
            return;
        } catch {
            // Fall through to alternate API shape.
        }
    }

    if (typeof app?.queuePromptWithIndex === "function") {
        try {
            await app.queuePromptWithIndex(0);
        } catch {
            // Ignore frontend API differences.
        }
    }
}

function installSamplerSeedButton() {
    app.registerExtension({
        name: EXTENSION_NAME,
        beforeRegisterNodeDef(nodeType, nodeData) {
            if (nodeData?.name !== TARGET_NODE_CLASS) {
                return;
            }

            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function onNodeCreatedWithManualSeedButton() {
                const output = typeof originalOnNodeCreated === "function"
                    ? originalOnNodeCreated.apply(this, arguments)
                    : undefined;

                if (!Array.isArray(this.widgets)) {
                    return output;
                }
                if (this.widgets.some((widget) => widget?.name === BUTTON_LABEL)) {
                    return output;
                }

                const seedWidget = this.widgets.find((widget) => widget?.name === SEED_WIDGET_NAME);
                if (!seedWidget) {
                    return output;
                }

                this.addWidget(
                    "button",
                    BUTTON_LABEL,
                    null,
                    async () => {
                        const { min, max } = getSeedWidgetBounds(seedWidget);
                        const current = Math.floor(toFiniteNumber(seedWidget.value, min));
                        let nextSeed = randomIntInRange(min, max);
                        if (min !== max && nextSeed === current) {
                            nextSeed = nextSeed === max ? min : nextSeed + 1;
                        }

                        if (setSeedValue(this, nextSeed)) {
                            await queueWorkflowIfEnabled();
                        }
                    },
                    { serialize: false },
                );

                return output;
            };
        },
    });
}

export {
    installSamplerSeedButton,
};
