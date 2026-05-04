from ..models import BubbaMetadata
from .overlay import _render_overlay_image_batch


class BubbaOverlayFromMetadata:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "metadata": ("BUBBA_METADATA",),
                "show_model": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "model_position": (
                    ["top", "bottom"],
                    {
                        "default": "top",
                    },
                ),
                "show_info": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "info_position": (
                    ["top", "bottom"],
                    {
                        "default": "top",
                    },
                ),
                "show_positive": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "positive_position": (
                    ["top", "bottom"],
                    {
                        "default": "bottom",
                    },
                ),
                "show_negative": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "negative_position": (
                    ["top", "bottom"],
                    {
                        "default": "bottom",
                    },
                ),
                "background_color": (
                    "STRING",
                    {
                        "default": "#000000AA",
                        "multiline": False,
                    },
                ),
                "font_size": (
                    "INT",
                    {
                        "default": 40,
                        "min": 10,
                        "max": 1000,
                        "control_after_generate": False,
                    },
                ),
                "overlay_mode": (
                    "BOOLEAN",
                    {
                        "default": True,
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "add_metadata_overlay"
    CATEGORY = "Bubba Nodes/Image/Overlay"
    DESCRIPTION = "Adds text overlay using fields extracted from Bubba Metadata Bundle object."

    @staticmethod
    def _extract_fields(metadata) -> tuple[str, str, str, str]:
        payload = BubbaMetadata.coerce(metadata)
        return (
            payload.model_name,
            payload.formatted_sampler_info(),
            payload.positive_prompt,
            payload.negative_prompt,
        )

    def add_metadata_overlay(
        self,
        image,
        metadata,
        show_model,
        model_position,
        show_info,
        info_position,
        show_positive,
        positive_position,
        show_negative,
        negative_position,
        background_color,
        font_size,
        overlay_mode,
    ):
        model_text, info_text, positive_text, negative_text = self._extract_fields(metadata)
        return _render_overlay_image_batch(
            image,
            model_text,
            info_text,
            positive_text,
            negative_text,
            show_model,
            show_info,
            show_positive,
            show_negative,
            model_position,
            info_position,
            positive_position,
            negative_position,
            background_color,
            font_size,
            overlay_mode,
        )
