const { app } = window.comfyAPI.app;

const EXTENSION_NAME = "bubba.CheckpointTreeCompat";
const TARGET_NODE_CLASS = "BubbaCheckpointLoader";
const PYSSSSS_CHECKPOINT_CLASS = "CheckpointLoader|pysssss";

function installCheckpointTieredMenus() {
	app.registerExtension({
		name: EXTENSION_NAME,
		beforeRegisterNodeDef(nodeType, nodeData) {
			if (nodeData?.name !== TARGET_NODE_CLASS) {
				return;
			}

			const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function onNodeCreatedWithPysssssCompat() {
				const result = typeof originalOnNodeCreated === "function"
					? originalOnNodeCreated.apply(this, arguments)
					: undefined;

				// Custom-Scripts betterCombos checks comfyClass string to decide whether to apply
				// folder-tree dropdown behavior for checkpoint widgets.
				if (!this.__bubbaOriginalComfyClass) {
					this.__bubbaOriginalComfyClass = this.comfyClass;
				}
				this.comfyClass = PYSSSSS_CHECKPOINT_CLASS;
				return result;
			};
		},
	});
}

export {
	installCheckpointTieredMenus,
};
