from dataclasses import dataclass
import re

import torch
from comfy_api.latest import IO

from ..models import BubbaPipe

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


class BubbaEmptyLatentBySize(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe = IO.Custom("BUBBA_PIPE")
        return IO.Schema(
            node_id="BubbaEmptyLatentBySize",
            display_name="Bubba Empty Latent (Preset Sizes)",
            category="Bubba Nodes/Generation",
            description="Creates an empty latent from a preset size with optional aspect-ratio inversion.",
            inputs=[
                IO.Combo.Input("size", options=_DIMENSION_OPTIONS, default="1:1 | 1024x1024 - SDXL"),
                IO.Boolean.Input("invert_aspect_ratio", default=False),
                IO.Int.Input("batch_size", default=1, min=1, max=4096, control_after_generate=False),
                pipe.Input("pipe", optional=True),
            ],
            outputs=[pipe.Output("pipe"), IO.Latent.Output("latent"), IO.Int.Output("width"), IO.Int.Output("height")],
        )

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

    @classmethod
    def execute(cls, size, invert_aspect_ratio, batch_size, pipe=None):
        source_pipe = BubbaPipe.coerce(pipe)
        width, height = cls._resolve_dimensions(size, invert_aspect_ratio)
        latent = torch.zeros([batch_size, 4, height // 8, width // 8], device="cpu")
        latent_payload = {"samples": latent}
        return IO.NodeOutput(source_pipe.updated(latent=latent_payload), latent_payload, width, height)
