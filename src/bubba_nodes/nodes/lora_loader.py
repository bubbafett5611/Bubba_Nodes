import folder_paths
from nodes import LoraLoader

from ..models import BubbaMetadata
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
                "model": ("MODEL", {"tooltip": "Diffusion model to apply the LoRA to."}),
                "clip": ("CLIP", {"tooltip": "CLIP model to apply the LoRA to."}),
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
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata object to update with this LoRA's name."},
                ),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "BUBBA_METADATA")
    RETURN_NAMES = ("model", "clip", "lora_name", "metadata")
    FUNCTION = "load_lora"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = (
        "Loads a LoRA and applies it to MODEL and CLIP. "
        "Records the LoRA name in metadata so it appears in overlays and saved image info. "
        "Chain multiple nodes to stack LoRAs — each appends to the metadata LoRA list."
    )

    def load_lora(self, model, clip, lora_name, strength_model, strength_clip, metadata=None):
        model_out, clip_out = self._loader.load_lora(model, clip, lora_name, strength_model, strength_clip)

        display_name = checkpoint_display_name(lora_name)
        existing = BubbaMetadata.coerce(metadata)
        updated_loras = list(existing.loras) + [display_name]
        updated_metadata = existing.updated(loras=updated_loras)

        return (model_out, clip_out, display_name, updated_metadata)
