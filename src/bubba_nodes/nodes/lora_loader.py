import folder_paths
from nodes import LoraLoader

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.checkpointing import checkpoint_display_name


class BubbaLoraLoader:
    """Loads a LoRA and applies it to MODEL and CLIP, recording the LoRA name in metadata.
    Multiple BubbaLoraLoader nodes can be chained; each appends its LoRA to the metadata list."""

    def __init__(self):
        self._loader = LoraLoader()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "lora_name": (
                    folder_paths.get_filename_list("loras"),
                    {"tooltip": "The LoRA file to load."},
                ),
                "strength_model": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": -100.0,
                        "max": 100.0,
                        "step": 0.01,
                        "tooltip": "How strongly to modify the diffusion model.",
                    },
                ),
                "strength_clip": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": -100.0,
                        "max": 100.0,
                        "step": 0.01,
                        "tooltip": "How strongly to modify the CLIP model.",
                    },
                ),
            },
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

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "model", "clip", "lora_name")
    FUNCTION = "load_lora"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = (
        "Loads a LoRA and applies it to MODEL and CLIP. "
        "Records the LoRA name in metadata so it appears in overlays and saved image info. "
        "Chain multiple nodes to stack LoRAs - each appends to the metadata LoRA list."
    )

    def load_lora(self, lora_name, strength_model, strength_clip, pipe=None, metadata=None, model=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_model = resolve_pipe_value(model, source_pipe.model, "model")
        resolved_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
        model_out, clip_out = self._loader.load_lora(resolved_model, resolved_clip, lora_name, strength_model, strength_clip)

        display_name = checkpoint_display_name(lora_name)
        existing = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_loras = list(existing.loras) + [display_name]
        updated_metadata = existing.updated(loras=updated_loras)
        updated_pipe = source_pipe.updated(model=model_out, clip=clip_out, metadata=updated_metadata)

        return (updated_pipe, updated_metadata, model_out, clip_out, display_name)
