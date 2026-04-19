from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
import torch

# TODO(new-node): Add a styled overlay preset node (cinematic, compact, streamer HUD) with reusable typography/layout presets.
# TODO(optimize): Evaluate moving text rasterization to cached layers keyed by text+font+width to reduce repeated draw cost.

from ..models import BubbaMetadata
from ..utils.image_ops import pil_to_tensor_like, tensor_sample_to_pil


def _compose_overlay_text(
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
):
    top_parts, bottom_parts = [], []
    if show_model and model_text.strip():
        (top_parts if model_position == "top" else bottom_parts).append(f"Model: {model_text.strip()}")
    if show_info and info_text.strip():
        (top_parts if info_position == "top" else bottom_parts).append(f"{info_text.strip()}")
    if show_positive and positive_text.strip():
        (top_parts if positive_position == "top" else bottom_parts).append(f"Positive:\n{positive_text.strip()}")
    if show_negative and negative_text.strip():
        (top_parts if negative_position == "top" else bottom_parts).append(f"Negative:\n{negative_text.strip()}")
    return "\n".join(top_parts), "\n".join(bottom_parts)


def _parse_overlay_rgba(color: str) -> tuple[int, int, int, int]:
    value = color.strip().lstrip("#")
    try:
        if len(value) == 6:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            return (r, g, b, 255)
        if len(value) == 8:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            a = int(value[6:8], 16)
            return (r, g, b, a)
    except ValueError:
        pass
    return (0, 0, 0, 170)


def _wrap_overlay_text_to_width(text: str, font, max_width: int) -> str:
    """Word-wrap each line so it fits within max_width pixels."""
    # TODO(optimize): Reuse a singleton probe canvas/draw context instead of allocating a new image each call.
    probe_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    result_lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            result_lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            w = probe_draw.textlength(test, font=font)
            if w <= max_width or not current:
                current = test
            else:
                result_lines.append(current)
                current = word
        if current:
            result_lines.append(current)
    return "\n".join(result_lines)


@lru_cache(maxsize=16)
def _get_overlay_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def _prepare_overlay_bar(text: str, font, max_text_w: int, pad_y: int):
    if not text.strip():
        return None, 0, 0
    wrapped = _wrap_overlay_text_to_width(text, font, max_text_w)
    probe_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    probe_draw = ImageDraw.Draw(probe_img)
    _, t, _, b = probe_draw.multiline_textbbox((0, 0), wrapped, font=font)
    text_h = max(1, b - t)
    bar_h = text_h + pad_y * 2
    text_y = max(0, (bar_h - text_h) // 2)
    return wrapped, bar_h, text_y


def _render_overlay_image_batch(
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
):
    top_text, bottom_text = _compose_overlay_text(
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
    )
    if not top_text.strip() and not bottom_text.strip():
        return (image,)

    rgba = _parse_overlay_rgba(background_color)
    font = _get_overlay_font(font_size)
    pad_x = max(8, int(font_size * 0.30))
    pad_y = max(6, int(font_size * 0.25))
    img_w = image[0].shape[1]
    max_text_w = max(1, img_w - 2 * pad_x)

    top_wrapped, top_bar_h, top_text_y = _prepare_overlay_bar(top_text, font, max_text_w, pad_y)
    bottom_wrapped, bottom_bar_h, bottom_text_y = _prepare_overlay_bar(bottom_text, font, max_text_w, pad_y)
    output = []

    for sample in image:
        src_pil = tensor_sample_to_pil(sample)
        src_rgba = src_pil.convert("RGBA")
        width, height = src_rgba.size

        if overlay_mode:
            overlay = Image.new("RGBA", src_rgba.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            if top_wrapped:
                draw.rectangle((0, 0, width, top_bar_h), fill=rgba)
                draw.multiline_text((pad_x, top_text_y), top_wrapped, font=font, fill=(255, 255, 255, 255))
            if bottom_wrapped:
                y0 = max(0, height - bottom_bar_h)
                draw.rectangle((0, y0, width, height), fill=rgba)
                draw.multiline_text((pad_x, y0 + bottom_text_y), bottom_wrapped, font=font, fill=(255, 255, 255, 255))
            composed = Image.alpha_composite(src_rgba, overlay)
        else:
            new_h = height + top_bar_h + bottom_bar_h
            composed = Image.new("RGBA", (width, new_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(composed)
            if top_wrapped:
                draw.rectangle((0, 0, width, top_bar_h), fill=rgba)
                draw.multiline_text((pad_x, top_text_y), top_wrapped, font=font, fill=(255, 255, 255, 255))
            composed.paste(src_rgba, (0, top_bar_h))
            if bottom_wrapped:
                y0 = top_bar_h + height
                draw.rectangle((0, y0, width, new_h), fill=rgba)
                draw.multiline_text((pad_x, y0 + bottom_text_y), bottom_wrapped, font=font, fill=(255, 255, 255, 255))

        output.append(
            pil_to_tensor_like(
                composed,
                sample,
                device=image.device,
                dtype=image.dtype,
            )
        )

    return (torch.stack(output, dim=0),)


class BubbaOverlay:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "model_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional model label text.",
                        "multiline": False,
                    },
                ),
                "info_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional generation info text.",
                        "multiline": False,
                    },
                ),
                "positive_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional positive prompt text.",
                        "multiline": True,
                    },
                ),
                "negative_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional negative prompt text.",
                        "multiline": True,
                    },
                ),
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
    FUNCTION = "add_text_overlay"
    CATEGORY = "Bubba Nodes/Image/Overlay"
    DESCRIPTION = "Adds an iTools-style text bar in overlay or underlay mode from individually toggled metadata fields."

    @staticmethod
    def _compose_text(
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
    ):
        return _compose_overlay_text(
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
        )

    @staticmethod
    def _parse_rgba(color: str) -> tuple[int, int, int, int]:
        return _parse_overlay_rgba(color)

    @staticmethod
    def _wrap_text_to_width(text: str, font, max_width: int) -> str:
        return _wrap_overlay_text_to_width(text, font, max_width)

    @staticmethod
    @lru_cache(maxsize=16)
    def _get_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return _get_overlay_font(font_size)

    def add_text_overlay(
        self,
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
    ):
        return _render_overlay_image_batch(
            image,
            model_text, info_text, positive_text, negative_text,
            show_model, show_info, show_positive, show_negative,
            model_position, info_position, positive_position, negative_position,
            background_color,
            font_size,
            overlay_mode,
        )


class BubbaOverlayFromMetadata:
    @classmethod
    def INPUT_TYPES(s):
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
            payload.sampler_info,
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
