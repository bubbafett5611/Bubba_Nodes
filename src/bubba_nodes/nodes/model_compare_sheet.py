from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from comfy_api.latest import IO
from PIL import Image, ImageDraw, ImageFont

from ..models import BubbaPipe
from ..utils.image_ops import tensor_sample_to_pil


_LAYOUTS = ["Auto", "Horizontal", "Vertical", "2x2 Grid"]
_FIT_MODES = ["Fit with padding", "Preserve size", "Crop to match"]
_LABEL_POSITIONS = ["Top left", "Top right", "Bottom left", "Bottom right"]
_BACKGROUNDS = ["Black", "Dark gray", "White"]


@dataclass(frozen=True)
class _CompareEntry:
    image: torch.Tensor
    label: str
    pipe: BubbaPipe


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _background_rgb(name: str) -> tuple[int, int, int]:
    return {"White": (255, 255, 255), "Dark gray": (32, 32, 32)}.get(name, (0, 0, 0))


def _layout_shape(layout: str, count: int) -> tuple[int, int]:
    if layout == "Horizontal":
        return 1, count
    if layout == "Vertical":
        return count, 1
    if layout == "2x2 Grid":
        return 2, 2
    if count <= 2:
        return 1, count
    return 2, 2


def _fit_image(image: Image.Image, size: tuple[int, int], mode: str, background: tuple[int, int, int]) -> Image.Image:
    source = image.convert("RGB")
    target_w, target_h = size
    if mode == "Preserve size":
        canvas = Image.new("RGB", size, background)
        x = (target_w - source.width) // 2
        y = (target_h - source.height) // 2
        canvas.paste(source, (x, y))
        return canvas

    source_ratio = source.width / max(1, source.height)
    target_ratio = target_w / max(1, target_h)
    cover = mode == "Crop to match"
    use_width = (source_ratio < target_ratio) if cover else (source_ratio > target_ratio)
    scale = target_w / source.width if use_width else target_h / source.height
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", size, background)
    canvas.paste(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
    return canvas


def _draw_label(image: Image.Image, text: str, position: str, font_size: int) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    label_font = _font(font_size)
    padding = max(4, font_size // 3)
    available_width = max(1, image.width - padding * 2)
    display_text = text
    while len(display_text) > 4 and draw.textbbox((0, 0), display_text, font=label_font)[2] > available_width:
        display_text = display_text[:-2].rstrip() + "…"
    left, top, right, bottom = draw.textbbox((0, 0), display_text, font=label_font)
    text_w, text_h = right - left, bottom - top
    if "right" in position.lower():
        x = image.width - text_w - padding * 2
    else:
        x = 0
    if "bottom" in position.lower():
        y = image.height - text_h - padding * 2
    else:
        y = 0
    draw.rectangle((x, y, x + text_w + padding * 2, y + text_h + padding * 2), fill=(0, 0, 0, 180))
    draw.text((x + padding - left, y + padding - top), display_text, font=label_font, fill=(255, 255, 255, 255))


class BubbaModelCompareSheet(IO.ComfyNode):
    """Compose up to four generated model results into a labeled comparison sheet."""

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaModelCompareSheet",
            display_name="Bubba Model Compare Sheet",
            category="Bubba Nodes/Image",
            description="Builds a labeled, save-ready comparison sheet from up to four generated model pipes or images.",
            inputs=[
                pipe.Input("pipe_1", optional=True),
                pipe.Input("pipe_2", optional=True),
                pipe.Input("pipe_3", optional=True),
                pipe.Input("pipe_4", optional=True),
                IO.Image.Input("image_1", optional=True),
                IO.Image.Input("image_2", optional=True),
                IO.Image.Input("image_3", optional=True),
                IO.Image.Input("image_4", optional=True),
                IO.Combo.Input("layout", options=_LAYOUTS, default="Auto"),
                IO.Combo.Input("fit_mode", options=_FIT_MODES, default="Fit with padding"),
                IO.Int.Input("gap", default=12, min=0, max=256),
                IO.Combo.Input("background", options=_BACKGROUNDS, default="Black"),
                IO.Int.Input("font_size", default=28, min=8, max=256),
                IO.Combo.Input("label_position", options=_LABEL_POSITIONS, default="Bottom left"),
            ],
            outputs=[
                pipe.Output("pipe"),
                IO.Image.Output("image"),
                metadata.Output("metadata"),
                IO.String.Output("info"),
            ],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        layout="Auto",
        fit_mode="Fit with padding",
        gap=12,
        background="Black",
        font_size=28,
        label_position="Bottom left",
        pipe_1=None,
        pipe_2=None,
        pipe_3=None,
        pipe_4=None,
        image_1=None,
        image_2=None,
        image_3=None,
        image_4=None,
    ):
        entries = cls._entries((pipe_1, pipe_2, pipe_3, pipe_4), (image_1, image_2, image_3, image_4))
        if not entries:
            raise ValueError("Bubba Model Compare Sheet needs at least one connected pipe or image.")

        pil_images = [tensor_sample_to_pil(entry.image[0]) for entry in entries]
        cell_size = (max(image.width for image in pil_images), max(image.height for image in pil_images))
        rows, columns = _layout_shape(layout, len(entries))
        spacing = max(0, int(gap))
        background_rgb = _background_rgb(background)
        sheet = Image.new(
            "RGB",
            (columns * cell_size[0] + max(0, columns - 1) * spacing, rows * cell_size[1] + max(0, rows - 1) * spacing),
            background_rgb,
        )
        for index, (entry, image) in enumerate(zip(entries, pil_images)):
            cell = _fit_image(image, cell_size, fit_mode, background_rgb)
            _draw_label(cell, entry.label, label_position, int(font_size))
            row, column = divmod(index, columns)
            sheet.paste(cell, (column * (cell_size[0] + spacing), row * (cell_size[1] + spacing)))

        reference = entries[0].image
        array = np.asarray(sheet, dtype=np.float32) / 255.0
        result_image = torch.from_numpy(array).to(device=reference.device, dtype=reference.dtype).unsqueeze(0)
        labels = [entry.label for entry in entries]
        metadata = entries[0].pipe.metadata.updated(model_name=" vs ".join(labels))
        result_pipe = entries[0].pipe.updated(image=result_image, metadata=metadata)
        info = f"Compared {len(entries)} models in {rows}x{columns}: " + " | ".join(labels)
        return IO.NodeOutput(result_pipe, result_image, metadata, info)

    @staticmethod
    def _entries(pipes, images) -> list[_CompareEntry]:
        entries = []
        for index, (pipe_value, image_override) in enumerate(zip(pipes, images), start=1):
            pipe = BubbaPipe.coerce(pipe_value)
            image = image_override if image_override is not None else pipe.image
            if image is None:
                continue
            if not isinstance(image, torch.Tensor) or image.ndim != 4 or image.shape[0] == 0:
                raise ValueError(f"Model compare image {index} must be a non-empty ComfyUI IMAGE batch.")
            label = pipe.metadata.model_name or f"Model {index}"
            entries.append(_CompareEntry(image=image, label=label, pipe=pipe.updated(image=image)))
        return entries
