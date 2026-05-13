from nodes import CheckpointLoaderSimple
from typing import Any, cast

from ..models import BubbaMetadata
from ..utils.checkpointing import checkpoint_display_name

# TODO(new-node): Add an advanced checkpoint node that also outputs model hash, filesize, and last-modified time.
# TODO(optimize): Cache repeated checkpoint loads by name for workflows that re-evaluate unchanged graphs.


class BubbaCheckpointLoader:
    @classmethod
    def INPUT_TYPES(cls):
        inputs = CheckpointLoaderSimple.INPUT_TYPES()
        # Add optional metadata input
        if "optional" not in inputs:
            inputs["optional"] = {}
        optional_inputs = cast(dict[str, Any], inputs["optional"])
        optional_inputs["metadata"] = (
            "BUBBA_METADATA",
            {
                "tooltip": "Optional metadata object to update with model name.",
            },
        )
        return inputs

    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING", "BUBBA_METADATA")
    RETURN_NAMES = ("model", "clip", "vae", "checkpoint_name", "metadata")
    FUNCTION = "load_checkpoint_with_name"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = "Loads a checkpoint, outputs the checkpoint name, and updates metadata with model information."

    def load_checkpoint_with_name(self, ckpt_name, metadata=None):
        model, clip, vae = CheckpointLoaderSimple().load_checkpoint(ckpt_name)

        # Update metadata with model name
        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            model_name=checkpoint_display_name(ckpt_name),
        )

        return (model, clip, vae, str(ckpt_name), updated_metadata)
