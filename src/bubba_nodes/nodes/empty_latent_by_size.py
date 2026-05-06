from dataclasses import dataclass
import re

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


_RAW_DIMENSION_GROUPS = (
    DimensionGroup(
        heading="1:1",
        presets=(
            DimensionPreset("SD 1.5", 512, 512),
            DimensionPreset("SD 2.x", 768, 768),
            DimensionPreset("SDXL", 1024, 1024),
            DimensionPreset("SDXL Large", 1536, 1536),
        ),
    ),
    DimensionGroup(
        heading="16:9",
        presets=(
            DimensionPreset("SD 1.5", 896, 512),
            DimensionPreset("SD 2.x", 1024, 576),
            DimensionPreset("SDXL", 1344, 768),
            DimensionPreset("SDXL Large", 1536, 864),
        ),
    ),
    DimensionGroup(
        heading="4:3",
        presets=(
            DimensionPreset("SD 1.5", 704, 512),
            DimensionPreset("SD 2.x", 1024, 768),
            DimensionPreset("SDXL", 1280, 960),
            DimensionPreset("SDXL Large", 1536, 1152),
        ),
    ),
    DimensionGroup(
        heading="3:2",
        presets=(
            DimensionPreset("SD 1.5", 768, 512),
            DimensionPreset("SD 2.x", 960, 640),
            DimensionPreset("SDXL", 1152, 768),
            DimensionPreset("SDXL Native", 1216, 832),
            DimensionPreset("SDXL Large", 1536, 1024),
        ),
    ),
    DimensionGroup(
        heading="21:9",
        presets=(
            DimensionPreset("SD 1.5", 1024, 448),
            DimensionPreset("SD 2.x", 1152, 512),
            DimensionPreset("SDXL", 1344, 576),
            DimensionPreset("SDXL Large", 1536, 640),
        ),
    ),
    DimensionGroup(
        heading="Other",
        presets=(
            DimensionPreset("SDXL", 1040, 800),
            DimensionPreset("SDXL", 1056, 832),
            DimensionPreset("SDXL", 1088, 832),
            DimensionPreset("SDXL", 1040, 896),
            DimensionPreset("SDXL", 1152, 896),
            DimensionPreset("SDXL", 1472, 704),
            DimensionPreset("SDXL", 1120, 928),
        ),
    ),
)


def _dedupe_dimension_groups(groups: tuple[DimensionGroup, ...]) -> tuple[DimensionGroup, ...]:
    seen_dimensions: set[tuple[int, int]] = set()
    deduped_groups: list[DimensionGroup] = []

    for group in groups:
        unique_presets: list[DimensionPreset] = []
        for preset in group.presets:
            key = (preset.width, preset.height)
            if key in seen_dimensions:
                continue
            seen_dimensions.add(key)
            unique_presets.append(preset)

        if unique_presets:
            deduped_groups.append(DimensionGroup(group.heading, tuple(unique_presets)))

    return tuple(deduped_groups)


_DIMENSION_GROUPS = _dedupe_dimension_groups(_RAW_DIMENSION_GROUPS)


def _preset_option_label(preset: DimensionPreset, group_heading: str) -> str:
    return f"{group_heading} | {preset.width}x{preset.height} - {preset.label}"


_DIMENSION_OPTIONS = [_preset_option_label(preset, group.heading) for group in _DIMENSION_GROUPS for preset in group.presets]


_DIMENSIONS_BY_OPTION = {
    _preset_option_label(preset, group.heading): (preset.width, preset.height) for group in _DIMENSION_GROUPS for preset in group.presets
}

_LEGACY_DIMENSION_RE = re.compile(r"\((\d+)x(\d+)\)")


class BubbaEmptyLatentBySize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "size": (
                    _DIMENSION_OPTIONS,
                    {
                        "default": "1:1 | 1024x1024 - SDXL",
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
        if size in _DIMENSIONS_BY_OPTION:
            width, height = _DIMENSIONS_BY_OPTION[size]
        else:
            # Backward compatibility for older workflow values like "Medium (1344x768)".
            match = _LEGACY_DIMENSION_RE.search(str(size or ""))
            if not match:
                raise ValueError(f"Invalid size preset selection: {size}")
            width, height = int(match.group(1)), int(match.group(2))

        if invert_aspect_ratio:
            width, height = height, width
        return (width, height)

    def build_empty_latent(self, size, invert_aspect_ratio, batch_size):
        # TODO(optimize): Reuse a cached zero-latent buffer for repeated shape requests to reduce allocator churn.
        width, height = self._resolve_dimensions(size, invert_aspect_ratio)
        latent = torch.zeros([batch_size, 4, height // 8, width // 8], device="cpu")
        return ({"samples": latent}, width, height)
