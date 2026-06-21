import folder_paths
from nodes import LoraLoader

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.checkpointing import checkpoint_display_name


_NONE_LORA = "None"
_LORA_SLOT_COUNT = 6


def _lora_choices() -> list[str]:
    choices = [_NONE_LORA]
    choices.extend(name for name in folder_paths.get_filename_list("loras") if name != _NONE_LORA)
    return choices


class BubbaLoraStack:
    """Applies several LoRAs in order while recording each applied LoRA in metadata."""

    def __init__(self):
        self._loader = LoraLoader()

    @classmethod
    def INPUT_TYPES(cls):
        required = {}
        for index in range(1, _LORA_SLOT_COUNT + 1):
            default_enabled = index == 1
            required[f"lora_{index}_name"] = (
                _lora_choices(),
                {"tooltip": f"LoRA file for stack slot {index}. Select None to skip this slot."},
            )
            required[f"lora_{index}_strength_model"] = (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": -100.0,
                    "max": 100.0,
                    "step": 0.01,
                    "tooltip": f"Model strength for LoRA slot {index}.",
                },
            )
            required[f"lora_{index}_strength_clip"] = (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": -100.0,
                    "max": 100.0,
                    "step": 0.01,
                    "tooltip": f"CLIP strength for LoRA slot {index}.",
                },
            )
            required[f"lora_{index}_enabled"] = (
                "BOOLEAN",
                {
                    "default": default_enabled,
                    "tooltip": f"Enable or bypass LoRA slot {index}.",
                },
            )

        return {
            "required": required,
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing the model and CLIP to update."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."},
                ),
                "model": ("MODEL", {"tooltip": "Optional model override. Overrides pipe.model when connected."}),
                "clip": ("CLIP", {"tooltip": "Optional CLIP override. Overrides pipe.clip when connected."}),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "model", "clip", "lora_names", "info")
    FUNCTION = "load_lora_stack"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = (
        "Applies up to six LoRAs to MODEL and CLIP in slot order. "
        "Explicit MODEL, CLIP, and metadata inputs override values from the pipe, and applied LoRA names are written back to pipe metadata."
    )

    def load_lora_stack(self, pipe=None, metadata=None, model=None, clip=None, **kwargs):
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
            current_model, current_clip = self._loader.load_lora(current_model, current_clip, lora_name, strength_model, strength_clip)
            applied_names.append(checkpoint_display_name(lora_name))

        updated_metadata = existing.updated(loras=list(existing.loras) + applied_names)
        updated_pipe = source_pipe.updated(model=current_model, clip=current_clip, metadata=updated_metadata)
        lora_names = ", ".join(applied_names)
        info = f"Applied {len(applied_names)} LoRA(s): {lora_names}" if applied_names else "No LoRAs applied."

        return (updated_pipe, updated_metadata, current_model, current_clip, lora_names, info)
