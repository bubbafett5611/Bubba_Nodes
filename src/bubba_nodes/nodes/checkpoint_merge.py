from comfy_api.latest import IO

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


def _merge_outputs():
    return [
        IO.Custom("BUBBA_PIPE").Output("pipe"),
        IO.Custom("BUBBA_CHECKPOINT_MERGE").Output("checkpoint_merge"),
        IO.Custom("BUBBA_METADATA").Output("metadata"),
        IO.Model.Output("model"),
        IO.Clip.Output("clip"),
        IO.Vae.Output("vae"),
        IO.String.Output("merge_recipe"),
        IO.String.Output("info"),
    ]


class BubbaCheckpointMerge(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaCheckpointMerge",
            display_name="Bubba Checkpoint Merge",
            category="Bubba Nodes/Merge",
            description="Blends two checkpoints while carrying unmatched keys from checkpoint A.",
            inputs=[
                IO.Combo.Input("checkpoint_a", options=checkpoint_choices()),
                IO.Combo.Input("checkpoint_b", options=checkpoint_choices()),
                IO.Float.Input("ratio", default=0.5, min=0.0, max=1.0, step=0.01),
                IO.Custom("BUBBA_PIPE").Input("pipe", optional=True),
                IO.Custom("BUBBA_METADATA").Input("metadata", optional=True),
            ],
            outputs=_merge_outputs(),
        )

    @classmethod
    def execute(cls, checkpoint_a, checkpoint_b, ratio, pipe=None, metadata=None):
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
        return IO.NodeOutput(updated_pipe, payload, updated_metadata, model, clip, vae, recipe_text(recipe), info)


class BubbaTripleCheckpointMerge(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        choices = checkpoint_choices()
        return IO.Schema(
            node_id="BubbaTripleCheckpointMerge",
            display_name="Bubba Triple Checkpoint Merge",
            category="Bubba Nodes/Merge",
            description="Performs A + (B - C) * strength checkpoint merging.",
            inputs=[
                IO.Combo.Input("checkpoint_a", options=choices),
                IO.Combo.Input("checkpoint_b", options=choices),
                IO.Combo.Input("checkpoint_c", options=choices),
                IO.Float.Input("strength", default=1.0, min=-2.0, max=2.0, step=0.01),
                IO.Custom("BUBBA_PIPE").Input("pipe", optional=True),
                IO.Custom("BUBBA_METADATA").Input("metadata", optional=True),
            ],
            outputs=_merge_outputs(),
        )

    @classmethod
    def execute(cls, checkpoint_a, checkpoint_b, checkpoint_c, strength, pipe=None, metadata=None):
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
        return IO.NodeOutput(updated_pipe, payload, updated_metadata, model, clip, vae, recipe_text(recipe), info)


class BubbaCheckpointFingerprint(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaCheckpointFingerprint",
            display_name="Bubba Checkpoint Fingerprint",
            category="Bubba Nodes/Merge",
            description="Outputs checkpoint hashes, size, modification time, and summary info.",
            inputs=[IO.Combo.Input("checkpoint", options=checkpoint_choices())],
            outputs=[
                IO.String.Output("checkpoint_name"),
                IO.String.Output("sha256"),
                IO.String.Output("short_hash"),
                IO.Int.Output("file_size_bytes"),
                IO.String.Output("modified_at"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(cls, checkpoint):
        details = checkpoint_fingerprint(checkpoint)
        info = (
            f"{details['checkpoint_name']}\n"
            f"Path: {details['path']}\n"
            f"SHA256: {details['sha256']}\n"
            f"Size: {details['file_size_bytes']} bytes\n"
            f"Modified: {details['modified_at']}"
        )
        return IO.NodeOutput(
            details["checkpoint_name"],
            details["sha256"],
            details["short_hash"],
            details["file_size_bytes"],
            details["modified_at"],
            info,
        )
