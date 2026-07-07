from comfy_api.latest import IO

from ..compat.core_nodes import LoraApplier
from ..compat.paths import get_filename_list
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.checkpointing import checkpoint_display_name


_NONE_LORA = "None"
_LORA_SLOT_COUNT = 6


def _lora_choices() -> list[str]:
    choices = [_NONE_LORA]
    choices.extend(name for name in get_filename_list("loras") if name != _NONE_LORA)
    return choices


class BubbaLoraStack(IO.ComfyNode):
    """Applies several LoRAs in order while recording each applied LoRA in metadata."""

    @classmethod
    def define_schema(cls):
        inputs = []
        for index in range(1, _LORA_SLOT_COUNT + 1):
            inputs.extend(
                [
                    IO.Combo.Input(f"lora_{index}_name", options=_lora_choices()),
                    IO.Float.Input(f"lora_{index}_strength_model", default=1.0, min=-100.0, max=100.0, step=0.01),
                    IO.Float.Input(f"lora_{index}_strength_clip", default=1.0, min=-100.0, max=100.0, step=0.01),
                    IO.Boolean.Input(f"lora_{index}_enabled", default=index == 1),
                ]
            )
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        inputs.extend(
            [
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Model.Input("model", optional=True),
                IO.Clip.Input("clip", optional=True),
            ]
        )
        return IO.Schema(
            node_id="BubbaLoraStack",
            display_name="Bubba LoRA Stack",
            category="Bubba Nodes/Generation",
            description="Applies up to six LoRAs in slot order and records them in metadata.",
            inputs=inputs,
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.String.Output("lora_names"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(cls, pipe=None, metadata=None, model=None, clip=None, **kwargs):
        source_pipe = BubbaPipe.coerce(pipe)
        current_model = resolve_pipe_value(model, source_pipe.model, "model")
        current_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
        existing = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)

        applied_names: list[str] = []
        for index in range(1, _LORA_SLOT_COUNT + 1):
            enabled = bool(kwargs.get(f"lora_{index}_enabled", True))
            lora_name = kwargs.get(f"lora_{index}_name", _NONE_LORA)
            if not enabled or not lora_name or lora_name == _NONE_LORA:
                continue

            strength_model = float(kwargs.get(f"lora_{index}_strength_model", 1.0))
            strength_clip = float(kwargs.get(f"lora_{index}_strength_clip", 1.0))
            current_model, current_clip = LoraApplier().apply(current_model, current_clip, lora_name, strength_model, strength_clip)
            applied_names.append(checkpoint_display_name(lora_name))

        updated_metadata = existing.updated(loras=list(existing.loras) + applied_names)
        updated_pipe = source_pipe.updated(model=current_model, clip=current_clip, metadata=updated_metadata)
        lora_names = ", ".join(applied_names)
        info = f"Applied {len(applied_names)} LoRA(s): {lora_names}" if applied_names else "No LoRAs applied."

        return IO.NodeOutput(updated_pipe, updated_metadata, current_model, current_clip, lora_names, info)
