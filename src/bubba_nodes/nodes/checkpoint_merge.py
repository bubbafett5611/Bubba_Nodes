from ..models import BubbaCheckpointMerge as BubbaCheckpointMergePayload
from ..models import BubbaMetadata, BubbaPipe
from ..utils.checkpoint_merge import (
    binary_merge_state_dict,
    checkpoint_choices,
    checkpoint_fingerprint,
    load_merged_checkpoint_objects,
    load_checkpoint_state_dict,
    recipe_metadata,
    recipe_text,
    sanitize_checkpoint_prefix,
    triple_merge_state_dict,
)
from ..utils.checkpointing import checkpoint_display_name


class BubbaCheckpointMerge:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_a": (
                    checkpoint_choices(),
                    {"tooltip": "Primary checkpoint. Non-mergeable keys are carried from this checkpoint."},
                ),
                "checkpoint_b": (checkpoint_choices(), {"tooltip": "Secondary checkpoint blended into checkpoint A."}),
                "ratio": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Blend amount for checkpoint B. 0 keeps A, 1 keeps B for matching tensors.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe to update with the merged model stack."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."},
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_CHECKPOINT_MERGE", "BUBBA_METADATA", "MODEL", "CLIP", "VAE", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "checkpoint_merge", "metadata", "model", "clip", "vae", "merge_recipe", "info")
    FUNCTION = "merge"
    CATEGORY = "Bubba Nodes/Merge"
    DESCRIPTION = "Blends two checkpoint files by merging matching floating tensors and carrying unmatched keys from checkpoint A."

    def merge(self, checkpoint_a, checkpoint_b, ratio, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        ratio = max(0.0, min(1.0, float(ratio)))
        sd_a, metadata_a = load_checkpoint_state_dict(checkpoint_a)
        sd_b, _metadata_b = load_checkpoint_state_dict(checkpoint_b)
        merged, stats = binary_merge_state_dict(sd_a, sd_b, ratio)

        name_a = checkpoint_display_name(checkpoint_a)
        name_b = checkpoint_display_name(checkpoint_b)
        suggested_name = sanitize_checkpoint_prefix(f"{name_a}_{1.0 - ratio:.2f}-{name_b}_{ratio:.2f}")
        recipe = {
            "type": "weighted",
            "checkpoint_a": checkpoint_a,
            "checkpoint_b": checkpoint_b,
            "ratio": ratio,
            "suggested_name": suggested_name,
            "stats": stats,
        }
        merge_metadata = dict(metadata_a)
        merge_metadata.update(recipe_metadata(recipe))
        payload = BubbaCheckpointMergePayload(
            state_dict=merged,
            recipe=recipe,
            metadata=merge_metadata,
            suggested_name=suggested_name,
        )
        model, clip, vae = load_merged_checkpoint_objects(merged, merge_metadata)
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            model_name=suggested_name,
        )
        updated_pipe = source_pipe.updated(
            model=model,
            clip=clip,
            vae=vae,
            positive=None,
            negative=None,
            metadata=updated_metadata,
        )
        info = (
            f"Merged {stats['merged_tensors']} tensor(s). "
            f"Carried {stats['carried_a_keys']} A-only key(s); skipped {stats['shape_mismatch_keys']} incompatible shared key(s)."
        )
        return (updated_pipe, payload, updated_metadata, model, clip, vae, recipe_text(recipe), info)


class BubbaTripleCheckpointMerge:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint_a": (checkpoint_choices(), {"tooltip": "Base checkpoint."}),
                "checkpoint_b": (checkpoint_choices(), {"tooltip": "Checkpoint to add."}),
                "checkpoint_c": (checkpoint_choices(), {"tooltip": "Checkpoint to subtract from B before adding to A."}),
                "strength": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": -2.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "Applies A + (B - C) * strength for matching tensors.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe to update with the merged model stack."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."},
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_CHECKPOINT_MERGE", "BUBBA_METADATA", "MODEL", "CLIP", "VAE", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "checkpoint_merge", "metadata", "model", "clip", "vae", "merge_recipe", "info")
    FUNCTION = "merge"
    CATEGORY = "Bubba Nodes/Merge"
    DESCRIPTION = "Performs a classic A + (B - C) * strength checkpoint merge."

    def merge(self, checkpoint_a, checkpoint_b, checkpoint_c, strength, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        strength = float(strength)
        sd_a, metadata_a = load_checkpoint_state_dict(checkpoint_a)
        sd_b, _metadata_b = load_checkpoint_state_dict(checkpoint_b)
        sd_c, _metadata_c = load_checkpoint_state_dict(checkpoint_c)

        merged, stats = triple_merge_state_dict(sd_a, sd_b, sd_c, strength)
        name_a = checkpoint_display_name(checkpoint_a)
        name_b = checkpoint_display_name(checkpoint_b)
        name_c = checkpoint_display_name(checkpoint_c)
        suggested_name = sanitize_checkpoint_prefix(f"{name_a}_plus_{name_b}_minus_{name_c}_{strength:.2f}")
        recipe = {
            "type": "difference",
            "checkpoint_a": checkpoint_a,
            "checkpoint_b": checkpoint_b,
            "checkpoint_c": checkpoint_c,
            "strength": strength,
            "suggested_name": suggested_name,
            "stats": stats,
        }
        merge_metadata = dict(metadata_a)
        merge_metadata.update(recipe_metadata(recipe))
        payload = BubbaCheckpointMergePayload(
            state_dict=merged,
            recipe=recipe,
            metadata=merge_metadata,
            suggested_name=suggested_name,
        )
        model, clip, vae = load_merged_checkpoint_objects(merged, merge_metadata)
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            model_name=suggested_name,
        )
        updated_pipe = source_pipe.updated(
            model=model,
            clip=clip,
            vae=vae,
            positive=None,
            negative=None,
            metadata=updated_metadata,
        )
        info = (
            f"Merged {stats['merged_tensors']} tensor(s) with A + (B - C) * {strength:g}. "
            f"Carried {stats['carried_a_keys']} A-only key(s); skipped {stats['shape_mismatch_keys']} incompatible key(s)."
        )
        return (updated_pipe, payload, updated_metadata, model, clip, vae, recipe_text(recipe), info)


class BubbaCheckpointFingerprint:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "checkpoint": (checkpoint_choices(), {"tooltip": "Checkpoint to fingerprint."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT", "STRING", "STRING")
    RETURN_NAMES = ("checkpoint_name", "sha256", "short_hash", "file_size_bytes", "modified_at", "info")
    FUNCTION = "fingerprint"
    CATEGORY = "Bubba Nodes/Merge"
    DESCRIPTION = "Outputs a checkpoint SHA256, short hash, file size, modification time, and summary info."

    def fingerprint(self, checkpoint):
        details = checkpoint_fingerprint(checkpoint)
        info = (
            f"{details['checkpoint_name']}\n"
            f"Path: {details['path']}\n"
            f"SHA256: {details['sha256']}\n"
            f"Size: {details['file_size_bytes']} bytes\n"
            f"Modified: {details['modified_at']}"
        )
        return (
            details["checkpoint_name"],
            details["sha256"],
            details["short_hash"],
            details["file_size_bytes"],
            details["modified_at"],
            info,
        )
