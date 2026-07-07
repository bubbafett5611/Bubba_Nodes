import numpy as np
from PIL import Image
import torch
from comfy_api.latest import IO

from ..models import BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.image_ops import pil_to_tensor_like, tensor_sample_to_pil


_ANCHOR_POINTS = [
    "top_left",
    "top_center",
    "top_right",
    "center_left",
    "center",
    "center_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
]


def _resolve_anchor_position(anchor: str, base_w: int, base_h: int, mark_w: int, mark_h: int) -> tuple[int, int]:
    if anchor == "top_left":
        return 0, 0
    if anchor == "top_center":
        return (base_w - mark_w) // 2, 0
    if anchor == "top_right":
        return base_w - mark_w, 0
    if anchor == "center_left":
        return 0, (base_h - mark_h) // 2
    if anchor == "center":
        return (base_w - mark_w) // 2, (base_h - mark_h) // 2
    if anchor == "center_right":
        return base_w - mark_w, (base_h - mark_h) // 2
    if anchor == "bottom_left":
        return 0, base_h - mark_h
    if anchor == "bottom_center":
        return (base_w - mark_w) // 2, base_h - mark_h
    if anchor == "bottom_right":
        return base_w - mark_w, base_h - mark_h
    return 0, 0


def _apply_alpha(image: Image.Image, alpha: float) -> Image.Image:
    clamped_alpha = max(0.0, min(1.0, float(alpha)))
    rgba = image.convert("RGBA")
    if clamped_alpha >= 1.0:
        return rgba

    channels = rgba.split()
    alpha_channel = channels[3].point(lambda value: int(value * clamped_alpha))
    rgba.putalpha(alpha_channel)
    return rgba


def _build_watermark_rgba(watermark, watermark_mask=None) -> Image.Image | None:
    if watermark is None or watermark.shape[0] == 0:
        return None

    mark_sample = np.clip(255.0 * watermark[0].cpu().numpy(), 0, 255).astype(np.uint8)
    mark_pil = Image.fromarray(mark_sample)
    if mark_pil.mode != "RGBA":
        mark_pil = mark_pil.convert("RGBA")

    if watermark_mask is not None and watermark_mask.shape[0] > 0:
        mask_sample = np.clip(255.0 * watermark_mask[0].cpu().numpy(), 0, 255).astype(np.uint8)
        if mask_sample.ndim == 3:
            mask_sample = mask_sample[..., 0]
        # ComfyUI mask convention is inverted relative to image alpha: 1.0 means masked/transparent.
        mask_sample = 255 - mask_sample
        mask_pil = Image.fromarray(mask_sample).convert("L")
        if mask_pil.size != mark_pil.size:
            mask_pil = mask_pil.resize(mark_pil.size, Image.Resampling.LANCZOS)
        mark_pil.putalpha(mask_pil)

    return mark_pil


def _overlay_watermark(base: Image.Image, mark: Image.Image, pos_x: int, pos_y: int) -> Image.Image:
    base_rgba = base.convert("RGBA")
    canvas = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    canvas.paste(mark, (pos_x, pos_y), mark)
    return Image.alpha_composite(base_rgba, canvas)


class BubbaWatermark(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe = IO.Custom("BUBBA_PIPE")
        return IO.Schema(
            node_id="BubbaWatermark",
            display_name="Bubba Watermark Overlay",
            category="Bubba Nodes/Image/Overlay",
            description="Adds a positioned, scaled watermark with optional transparency mask.",
            inputs=[
                IO.Image.Input("watermark"),
                IO.Boolean.Input("enabled", default=True),
                IO.Combo.Input("anchor", options=_ANCHOR_POINTS, default="bottom_right"),
                IO.Float.Input("image_scale", default=1.0, min=0.01, max=10.0, step=0.01),
                IO.Float.Input("alpha", default=1.0, min=0.0, max=1.0, step=0.01),
                IO.Int.Input("x_offset", default=0, min=-8192, max=8192),
                IO.Int.Input("y_offset", default=0, min=-8192, max=8192),
                pipe.Input("pipe", optional=True),
                IO.Image.Input("image", optional=True),
                IO.Mask.Input("watermark_mask", optional=True),
            ],
            outputs=[pipe.Output("pipe"), IO.Image.Output("image")],
        )

    @staticmethod
    def _resolve_anchor_position(anchor: str, base_w: int, base_h: int, mark_w: int, mark_h: int) -> tuple[int, int]:
        return _resolve_anchor_position(anchor, base_w, base_h, mark_w, mark_h)

    @classmethod
    def execute(cls, watermark, enabled, anchor, image_scale, alpha, x_offset, y_offset, pipe=None, image=None, watermark_mask=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_image = resolve_pipe_value(image, source_pipe.image, "image")
        if not enabled:
            return IO.NodeOutput(source_pipe.updated(image=resolved_image), resolved_image)

        mark_pil = _build_watermark_rgba(watermark, watermark_mask=watermark_mask)
        if mark_pil is None:
            return IO.NodeOutput(source_pipe.updated(image=resolved_image), resolved_image)

        scale = max(0.01, float(image_scale))
        scaled_w = max(1, int(round(mark_pil.width * scale)))
        scaled_h = max(1, int(round(mark_pil.height * scale)))
        if (scaled_w, scaled_h) != mark_pil.size:
            mark_pil = mark_pil.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        mark_pil = _apply_alpha(mark_pil, alpha)

        output = []
        for sample in resolved_image:
            src_pil = tensor_sample_to_pil(sample)
            base_w, base_h = src_pil.size

            anchor_x, anchor_y = _resolve_anchor_position(anchor, base_w, base_h, mark_pil.width, mark_pil.height)
            pos_x = int(anchor_x + x_offset)
            pos_y = int(anchor_y + y_offset)

            composed = _overlay_watermark(src_pil, mark_pil, pos_x, pos_y)

            output.append(
                pil_to_tensor_like(
                    composed,
                    sample,
                    device=resolved_image.device,
                    dtype=resolved_image.dtype,
                )
            )

        output_image = torch.stack(output, dim=0)
        return IO.NodeOutput(source_pipe.updated(image=output_image), output_image)
