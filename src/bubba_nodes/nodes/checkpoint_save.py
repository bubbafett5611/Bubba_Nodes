from pathlib import Path

from ..models import BubbaCheckpointMerge
from ..utils.checkpoint_merge import ensure_safetensors_name, recipe_text, save_checkpoint_merge, sanitize_checkpoint_prefix


class BubbaSaveCheckpoint:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_merge": ("BUBBA_CHECKPOINT_MERGE", {"tooltip": "Merged checkpoint payload to save."}),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Relative filename inside the ComfyUI checkpoints folder. Leave blank to use the merge recipe suggestion.",
                    },
                ),
                "overwrite": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Overwrite an existing checkpoint with the same filename. When disabled, a numeric suffix is added.",
                    },
                ),
                "save_recipe_sidecar": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Save a JSON sidecar next to the checkpoint containing the merge recipe.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("checkpoint_name", "checkpoint_path", "info")
    FUNCTION = "save"
    CATEGORY = "Bubba Nodes/Merge"
    OUTPUT_NODE = True
    DESCRIPTION = "Saves a Bubba checkpoint merge payload as a safetensors checkpoint in the ComfyUI checkpoints folder."

    def save(self, checkpoint_merge, filename_prefix="", overwrite=False, save_recipe_sidecar=True):
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
        return (relative_name, str(target), info)


class BubbaMergeNamingHelper:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_name": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional manual base name. Leave blank to use checkpoint_merge.suggested_name.",
                    },
                ),
                "folder": (
                    "STRING",
                    {
                        "default": "Bubba_Merges",
                        "tooltip": "Optional subfolder inside the ComfyUI checkpoints folder.",
                    },
                ),
                "suffix": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional suffix appended before .safetensors.",
                    },
                ),
            },
            "optional": {
                "checkpoint_merge": ("BUBBA_CHECKPOINT_MERGE", {"tooltip": "Optional merge payload to name."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("filename_prefix", "info")
    FUNCTION = "build_name"
    CATEGORY = "Bubba Nodes/Merge"
    DESCRIPTION = "Builds a clean relative checkpoint filename for merged checkpoints."

    def build_name(self, base_name="", folder="Bubba_Merges", suffix="", checkpoint_merge=None):
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
        return (filename, info)
