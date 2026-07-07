const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.SamplerSeedButton";
const TARGET_NODE_CLASSES = new Set(["BubbaKSampler", "BubbaSeedControl"]);
const SEED_WIDGET_NAME = "seed";
const BUTTON_LABEL = "Manual Random Seed";
const AUTO_QUEUE_KEY = "bubba.KSampler.ManualSeed.AutoQueue";
const FIXED_CONTROL_VALUE = "fixed";
const MANUAL_SEED_MAX = 1125899906842624; // EasyUse-style 2^50 cap.

function migrateLegacySeedControlOutputs(node) {
    if (node?.comfyClass !== "BubbaSeedControl" || !Array.isArray(node.outputs)) {
        return;
    }

    const names = node.outputs.map((output) => output?.name);
    if (names[0] === "pipe" && names[1] === "metadata" && names[2] === "seed") {
        // removeOutput shifts surviving link origin slots, preserving old seed/info wires.
        node.removeOutput(1);
        node.removeOutput(0);
    }

    const links = app?.graph?.links;
    if (!links || !Array.isArray(node.outputs) || node.outputs.length < 2) {
        return;
    }

    // Fallback for frontend builds that already restored the new output definitions
    // but retained the legacy numeric origin slots in the graph link table.
    const ownLinks = Object.values(links).filter((link) => String(link?.origin_id) === String(node.id));
    let changed = false;
    for (const link of ownLinks) {
        if (link.origin_slot === 2 || link.origin_slot === 3) {
            link.origin_slot -= 2;
            changed = true;
        }
    }
    if (!changed) {
        return;
    }

    for (const output of node.outputs) {
        output.links = [];
    }
    for (const link of ownLinks) {
        if (link.origin_slot >= 0 && link.origin_slot < node.outputs.length) {
            node.outputs[link.origin_slot].links.push(link.id);
        }
    }
    node.setDirtyCanvas?.(true, true);
}

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
            if (!TARGET_NODE_CLASSES.has(nodeData?.name)) {
                return;
            }

            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            const originalOnConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function onConfigureWithSeedMigration() {
                const output = typeof originalOnConfigure === "function"
                    ? originalOnConfigure.apply(this, arguments)
                    : undefined;
                migrateLegacySeedControlOutputs(this);
                return output;
            };
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
