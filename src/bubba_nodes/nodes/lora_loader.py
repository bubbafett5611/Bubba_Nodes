from comfy_api.latest import IO

from ..compat.core_nodes import LoraApplier
from ..compat.paths import get_filename_list
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.checkpointing import checkpoint_display_name


class BubbaLoraLoader(IO.ComfyNode):
    """Loads a LoRA and applies it to MODEL and CLIP, recording the LoRA name in metadata.
    Multiple BubbaLoraLoader nodes can be chained; each appends its LoRA to the metadata list."""

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaLoraLoader",
            display_name="Bubba LoRA Loader",
            category="Bubba Nodes/Generation",
            description="Applies a LoRA to MODEL and CLIP and records it in metadata.",
            inputs=[
                IO.Combo.Input("lora_name", options=get_filename_list("loras")),
                IO.Float.Input("strength_model", default=1.0, min=-100.0, max=100.0, step=0.01),
                IO.Float.Input("strength_clip", default=1.0, min=-100.0, max=100.0, step=0.01),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Model.Input("model", optional=True),
                IO.Clip.Input("clip", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.String.Output("lora_name"),
            ],
        )

    @classmethod
    def execute(cls, lora_name, strength_model, strength_clip, pipe=None, metadata=None, model=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_model = resolve_pipe_value(model, source_pipe.model, "model")
        resolved_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
        model_out, clip_out = LoraApplier().apply(resolved_model, resolved_clip, lora_name, strength_model, strength_clip)

        display_name = checkpoint_display_name(lora_name)
        existing = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_loras = list(existing.loras) + [display_name]
        updated_metadata = existing.updated(loras=updated_loras)
        updated_pipe = source_pipe.updated(model=model_out, clip=clip_out, metadata=updated_metadata)

        return IO.NodeOutput(updated_pipe, updated_metadata, model_out, clip_out, display_name)
