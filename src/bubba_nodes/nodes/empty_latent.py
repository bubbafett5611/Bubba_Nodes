import torch


_DIMENSION_OPTIONS = [
    "--- Square ---",
    "Tiny (512x512)",
    "Small (768x768)",
    "Medium (1024x1024)",
    "Large (1536x1536)",
    "--- 16:9 ---",
    "Tiny (896x512)",
    "Small (1024x576)",
    "Medium (1344x768)",
    "Large (1536x864)",
    "--- 4:3 ---",
    "Tiny (704x512)",
    "Small (1024x768)",
    "Medium (1280x960)",
    "Large (1536x1152)",
    "--- 3:2 ---",
    "Tiny (768x512)",
    "Small (960x640)",
    "Medium (1152x768)",
    "Large (1536x1024)",
    "--- 21:9 ---",
    "Tiny (1152x512)",
    "Small (1024x448)",
    "Medium (1344x576)",
    "Large (1536x640)",
]


_DIMENSIONS_BY_OPTION = {
    "Tiny (512x512)": (512, 512),
    "Small (768x768)": (768, 768),
    "Medium (1024x1024)": (1024, 1024),
    "Large (1536x1536)": (1536, 1536),
    "Tiny (896x512)": (896, 512),
    "Small (1024x576)": (1024, 576),
    "Medium (1344x768)": (1344, 768),
    "Large (1536x864)": (1536, 864),
    "Tiny (704x512)": (704, 512),
    "Small (1024x768)": (1024, 768),
    "Medium (1280x960)": (1280, 960),
    "Large (1536x1152)": (1536, 1152),
    "Tiny (768x512)": (768, 512),
    "Small (960x640)": (960, 640),
    "Medium (1152x768)": (1152, 768),
    "Large (1536x1024)": (1536, 1024),
    "Tiny (1152x512)": (1152, 512),
    "Small (1024x448)": (1024, 448),
    "Medium (1344x576)": (1344, 576),
    "Large (1536x640)": (1536, 640),
}


class BubbaEmptyLatentBySize:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "size": (
                    _DIMENSION_OPTIONS,
                    {
                        "default": "Medium (1024x1024)",
                        "tooltip": "Preset output dimensions from baked-in size list.",
                    },
                ),
                "invert_aspect_ratio": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Swap width and height for the selected size.",
                    },
                ),
                "batch_size": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 4096,
                        "control_after_generate": False,
                        "tooltip": "Number of latent samples to create.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("LATENT", "INT", "INT")
    RETURN_NAMES = ("latent", "width", "height")
    FUNCTION = "build_empty_latent"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Creates an empty latent from a baked-in preset size list with optional aspect-ratio inversion."

    @staticmethod
    def _resolve_dimensions(size: str, invert_aspect_ratio: bool) -> tuple[int, int]:
        # If a section header is chosen, fall back to a safe default.
        width, height = _DIMENSIONS_BY_OPTION.get(size, (1024, 1024))
        if invert_aspect_ratio:
            width, height = height, width
        return (width, height)

    def build_empty_latent(self, size, invert_aspect_ratio, batch_size):
        width, height = self._resolve_dimensions(size, invert_aspect_ratio)
        latent = torch.zeros([batch_size, 4, height // 8, width // 8], device="cpu")
        return ({"samples": latent}, width, height)
