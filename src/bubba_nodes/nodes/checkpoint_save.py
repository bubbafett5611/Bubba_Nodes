from pathlib import Path
from comfy_api.latest import IO

from ..models import BubbaCheckpointMerge
from ..utils.checkpoint_merge import ensure_safetensors_name, recipe_text, save_checkpoint_merge, sanitize_checkpoint_prefix


class BubbaSaveCheckpoint(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        merge = IO.Custom("BUBBA_CHECKPOINT_MERGE")
        return IO.Schema(
            node_id="BubbaSaveCheckpoint",
            display_name="Bubba Save Checkpoint",
            category="Bubba Nodes/Merge",
            description="Saves a Bubba checkpoint merge payload as a safetensors checkpoint.",
            inputs=[
                merge.Input("checkpoint_merge"),
                IO.String.Input("filename_prefix", default=""),
                IO.Boolean.Input("overwrite", default=False),
                IO.Boolean.Input("save_recipe_sidecar", default=True),
            ],
            outputs=[IO.String.Output("checkpoint_name"), IO.String.Output("checkpoint_path"), IO.String.Output("info")],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, checkpoint_merge, filename_prefix="", overwrite=False, save_recipe_sidecar=True):
        payload = BubbaCheckpointMerge.coerce(checkpoint_merge)
        prefix = sanitize_checkpoint_prefix(filename_prefix or payload.suggested_name or "bubba_merge")
        target, relative_name = save_checkpoint_merge(
            payload.state_dict,
            prefix,
            metadata=payload.metadata,
            overwrite=bool(overwrite),
        )

        if save_recipe_sidecar:
            sidecar = Path(target).with_suffix(".bubba_recipe.json")
            sidecar.write_text(recipe_text(payload.recipe), encoding="utf-8")

        info = f"Saved checkpoint: {relative_name}\nPath: {target}\nTensors: {len(payload.state_dict)}"
        return IO.NodeOutput(relative_name, str(target), info)


class BubbaMergeNamingHelper(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaMergeNamingHelper",
            display_name="Bubba Merge Naming Helper",
            category="Bubba Nodes/Merge",
            description="Builds a clean relative checkpoint filename for merged checkpoints.",
            inputs=[
                IO.String.Input("base_name", default=""),
                IO.String.Input("folder", default="Bubba_Merges"),
                IO.String.Input("suffix", default=""),
                IO.Custom("BUBBA_CHECKPOINT_MERGE").Input("checkpoint_merge", optional=True),
            ],
            outputs=[IO.String.Output("filename_prefix"), IO.String.Output("info")],
        )

    @classmethod
    def execute(cls, base_name="", folder="Bubba_Merges", suffix="", checkpoint_merge=None):
        suggested = ""
        recipe = {}
        if checkpoint_merge is not None:
            payload = BubbaCheckpointMerge.coerce(checkpoint_merge)
            suggested = payload.suggested_name
            recipe = payload.recipe

        base = sanitize_checkpoint_prefix(base_name or suggested or recipe.get("suggested_name") or "bubba_merge")
        clean_folder = sanitize_checkpoint_prefix(folder, fallback="").strip("/")
        clean_suffix = sanitize_checkpoint_prefix(suffix, fallback="").strip("/")
        if clean_suffix:
            base = f"{base}_{clean_suffix}"
        prefix = f"{clean_folder}/{base}" if clean_folder else base
        filename = ensure_safetensors_name(prefix)
        info = f"Checkpoint filename: {filename}"
        if recipe:
            info += f"\nRecipe type: {recipe.get('type', 'unknown')}"
        return IO.NodeOutput(filename, info)
