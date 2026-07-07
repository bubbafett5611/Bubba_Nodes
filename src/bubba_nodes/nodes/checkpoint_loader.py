from comfy_api.latest import IO

from ..compat.core_nodes import load_checkpoint
from ..compat.paths import get_filename_list
from ..models import BubbaMetadata, BubbaPipe
from ..utils.checkpointing import checkpoint_display_name

# TODO(new-node): Add an advanced checkpoint node that also outputs model hash, filesize, and last-modified time.


class BubbaCheckpointLoader(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaCheckpointLoader",
            display_name="Bubba Checkpoint Loader",
            category="Bubba Nodes/Generation",
            description="Loads a checkpoint and updates the pipe and model metadata.",
            inputs=[
                IO.Combo.Input("ckpt_name", options=get_filename_list("checkpoints")),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.Vae.Output("vae"),
                IO.String.Output("checkpoint_name"),
            ],
        )

    @classmethod
    def execute(cls, ckpt_name, pipe=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        model, clip, vae = load_checkpoint(ckpt_name)

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

        return IO.NodeOutput(updated_pipe, updated_metadata, model, clip, vae, str(ckpt_name))
