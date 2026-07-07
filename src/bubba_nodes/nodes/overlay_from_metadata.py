from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
import torch
from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
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
    top_parts: list[str] = []
    bottom_parts: list[str] = []
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
            new_h = int(height + top_bar_h + bottom_bar_h)
            composed = Image.new("RGBA", (width, new_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(composed)
            if top_wrapped:
                draw.rectangle((0, 0, width, top_bar_h), fill=rgba)
                draw.multiline_text((pad_x, top_text_y), top_wrapped, font=font, fill=(255, 255, 255, 255))
            composed.paste(src_rgba, (0, int(top_bar_h)))
            if bottom_wrapped:
                y0 = int(top_bar_h + height)
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


class BubbaOverlayFromMetadata(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pos = ["top", "bottom"]
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaOverlayFromMetadata",
            display_name="Bubba Add Text Overlay (Metadata)",
            category="Bubba Nodes/Image/Overlay",
            description="Adds an image overlay from Bubba metadata fields.",
            inputs=[
                IO.Boolean.Input("show_model", default=False),
                IO.Combo.Input("model_position", options=pos, default="top"),
                IO.Boolean.Input("show_info", default=False),
                IO.Combo.Input("info_position", options=pos, default="top"),
                IO.Boolean.Input("show_positive", default=False),
                IO.Combo.Input("positive_position", options=pos, default="bottom"),
                IO.Boolean.Input("show_negative", default=False),
                IO.Combo.Input("negative_position", options=pos, default="bottom"),
                IO.String.Input("background_color", default="#000000AA"),
                IO.Int.Input("font_size", default=40, min=10, max=1000, control_after_generate=False),
                IO.Boolean.Input("overlay_mode", default=True),
                pipe.Input("pipe", optional=True),
                IO.Image.Input("image", optional=True),
                metadata.Input("metadata", optional=True),
            ],
            outputs=[pipe.Output("pipe"), IO.Image.Output("image"), metadata.Output("metadata")],
        )

    @staticmethod
    def _extract_fields(metadata) -> tuple[str, str, str, str]:
        payload = BubbaMetadata.coerce(metadata)
        return (
            payload.model_name,
            payload.formatted_sampler_info(),
            payload.positive_prompt,
            payload.negative_prompt,
        )

    @classmethod
    def execute(
        cls,
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
        pipe=None,
        metadata=None,
        image=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_image = resolve_pipe_value(image, source_pipe.image, "image")
        resolved_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        model_text, info_text, positive_text, negative_text = cls._extract_fields(resolved_metadata)
        (output_image,) = _render_overlay_image_batch(
            resolved_image,
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
        return IO.NodeOutput(source_pipe.updated(image=output_image, metadata=resolved_metadata), output_image, resolved_metadata)
