from nodes import CheckpointLoaderSimple
from typing import Any, cast

from ..models import BubbaMetadata, BubbaPipe
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
        existing_optional = dict(optional_inputs)
        optional_inputs.clear()
        optional_inputs["pipe"] = (
            "BUBBA_PIPE",
            {
                "tooltip": "Optional incoming pipe. Keeps non-model context while replacing model, CLIP, VAE, and model metadata.",
            },
        )
        optional_inputs["metadata"] = (
            "BUBBA_METADATA",
            {
                "tooltip": "Optional metadata override. Overrides pipe.metadata when connected.",
            },
        )
        optional_inputs.update(existing_optional)
        return inputs

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "model", "clip", "vae", "checkpoint_name")
    FUNCTION = "load_checkpoint_with_name"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = "Loads a checkpoint, outputs the checkpoint name, and updates metadata with model information."

    def load_checkpoint_with_name(self, ckpt_name, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        model, clip, vae = CheckpointLoaderSimple().load_checkpoint(ckpt_name)

        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            model_name=checkpoint_display_name(ckpt_name),
        )
        updated_pipe = source_pipe.updated(
            model=model,
            clip=clip,
            vae=vae,
            positive=None,
            negative=None,
            metadata=updated_metadata,
        )

        return (updated_pipe, updated_metadata, model, clip, vae, str(ckpt_name))
