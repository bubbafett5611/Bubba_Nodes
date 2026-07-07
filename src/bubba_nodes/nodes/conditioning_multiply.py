from __future__ import annotations

from comfy_api.latest import IO

from ..compat.core_nodes import multiply_conditioning
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value


_MODES = ["both", "positive", "negative"]


class BubbaConditioningMultiply(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaConditioningMultiply",
            display_name="Bubba Conditioning Multiply",
            category="Bubba Nodes/Generation",
            description="Pipe-aware conditioning scaling for positive and negative branches.",
            inputs=[
                IO.Float.Input("positive_strength", default=1.0, min=-100.0, max=100.0, step=0.01),
                IO.Float.Input("negative_strength", default=1.0, min=-100.0, max=100.0, step=0.01),
                IO.Combo.Input("mode", options=_MODES),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Conditioning.Input("positive", optional=True),
                IO.Conditioning.Input("negative", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(cls, positive_strength, negative_strength, mode, pipe=None, metadata=None, positive=None, negative=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_positive = resolve_pipe_value(positive, source_pipe.positive, "positive conditioning")
        resolved_negative = resolve_pipe_value(negative, source_pipe.negative, "negative conditioning")
        selected_mode = mode if mode in _MODES else "both"

        output_positive = (
            multiply_conditioning(resolved_positive, float(positive_strength))
            if selected_mode in {"both", "positive"}
            else resolved_positive
        )
        output_negative = (
            multiply_conditioning(resolved_negative, float(negative_strength))
            if selected_mode in {"both", "negative"}
            else resolved_negative
        )

        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_pipe = source_pipe.updated(positive=output_positive, negative=output_negative, metadata=updated_metadata)
        info = f"Conditioning multiply mode={selected_mode}; positive={positive_strength:g}; negative={negative_strength:g}"
        return IO.NodeOutput(updated_pipe, updated_metadata, output_positive, output_negative, info)
