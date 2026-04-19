from dataclasses import dataclass

import torch

# TODO(new-feature): Allow user-defined size presets loaded from a JSON file so artists can share profile packs.
# TODO(new-node): Add a companion latent size recommender node that suggests dimensions from target aspect ratio + VRAM budget.


@dataclass(frozen=True)
class DimensionPreset:
    label: str
    width: int
    height: int


@dataclass(frozen=True)
class DimensionGroup:
    heading: str
    presets: tuple[DimensionPreset, ...]


_DIMENSION_GROUPS = (
    DimensionGroup(
        heading="Square",
        presets=(
            DimensionPreset("Tiny", 512, 512),
            DimensionPreset("Small", 768, 768),
            DimensionPreset("Medium", 1024, 1024),
            DimensionPreset("Large", 1536, 1536),
        ),
    ),
    DimensionGroup(
        heading="16:9",
        presets=(
            DimensionPreset("Tiny", 896, 512),
            DimensionPreset("Small", 1024, 576),
            DimensionPreset("Medium", 1344, 768),
            DimensionPreset("Large", 1536, 864),
        ),
    ),
    DimensionGroup(
        heading="4:3",
        presets=(
            DimensionPreset("Tiny", 704, 512),
            DimensionPreset("Small", 1024, 768),
            DimensionPreset("Medium", 1280, 960),
            DimensionPreset("Large", 1536, 1152),
        ),
    ),
    DimensionGroup(
        heading="3:2",
        presets=(
            DimensionPreset("Tiny", 768, 512),
            DimensionPreset("Small", 960, 640),
            DimensionPreset("Medium", 1152, 768),
            DimensionPreset("Large", 1536, 1024),
        ),
    ),
    DimensionGroup(
        heading="21:9",
        presets=(
            DimensionPreset("Tiny", 1152, 512),
            DimensionPreset("Small", 1024, 448),
            DimensionPreset("Medium", 1344, 576),
            DimensionPreset("Large", 1536, 640),
        ),
    ),
)


def _preset_option_label(preset: DimensionPreset) -> str:
    return f"{preset.label} ({preset.width}x{preset.height})"


_DIMENSION_OPTIONS = [
    option
    for group in _DIMENSION_GROUPS
    for option in ([f"--- {group.heading} ---"] + [_preset_option_label(preset) for preset in group.presets])
]


_DIMENSIONS_BY_OPTION = {
    _preset_option_label(preset): (preset.width, preset.height)
    for group in _DIMENSION_GROUPS
    for preset in group.presets
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
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = "Creates an empty latent from a baked-in preset size list with optional aspect-ratio inversion."

    @staticmethod
    def _resolve_dimensions(size: str, invert_aspect_ratio: bool) -> tuple[int, int]:
        if size not in _DIMENSIONS_BY_OPTION:
            raise ValueError(f"Invalid size preset selection: {size}")

        width, height = _DIMENSIONS_BY_OPTION[size]
        if invert_aspect_ratio:
            width, height = height, width
        return (width, height)

    def build_empty_latent(self, size, invert_aspect_ratio, batch_size):
        # TODO(optimize): Reuse a cached zero-latent buffer for repeated shape requests to reduce allocator churn.
        width, height = self._resolve_dimensions(size, invert_aspect_ratio)
        latent = torch.zeros([batch_size, 4, height // 8, width // 8], device="cpu")
        return ({"samples": latent}, width, height)
