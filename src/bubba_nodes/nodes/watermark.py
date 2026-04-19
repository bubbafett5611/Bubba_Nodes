import numpy as np
from PIL import Image
import torch

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


class BubbaWatermark:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "watermark": ("IMAGE",),
                "enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Disable to bypass watermark and return the original image unchanged.",
                    },
                ),
                "anchor": (
                    _ANCHOR_POINTS,
                    {
                        "default": "bottom_right",
                        "tooltip": "Anchor position for placing the watermark image.",
                    },
                ),
                "image_scale": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.01,
                        "max": 10.0,
                        "step": 0.01,
                        "tooltip": "Scale multiplier where 0.5 = 50% size and 2.0 = 200% size.",
                        "control_after_generate": False,
                    },
                ),
                "alpha": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Final watermark opacity. 0.0 is transparent, 1.0 is fully visible.",
                        "control_after_generate": False,
                    },
                ),
                "x_offset": (
                    "INT",
                    {
                        "default": 0,
                        "min": -8192,
                        "max": 8192,
                    },
                ),
                "y_offset": (
                    "INT",
                    {
                        "default": 0,
                        "min": -8192,
                        "max": 8192,
                    },
                ),
            },
            "optional": {
                "watermark_mask": (
                    "MASK",
                    {
                        "tooltip": "Optional mask from Load Image to preserve PNG transparency.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "add_watermark"
    CATEGORY = "Bubba Nodes/Image/Overlay"
    DESCRIPTION = "Adds a watermark image using anchor position, scale, opacity, and XY offsets. Connect Load Image MASK to preserve transparency."

    @staticmethod
    def _resolve_anchor_position(anchor: str, base_w: int, base_h: int, mark_w: int, mark_h: int) -> tuple[int, int]:
        return _resolve_anchor_position(anchor, base_w, base_h, mark_w, mark_h)

    def add_watermark(self, image, watermark, enabled, anchor, image_scale, alpha, x_offset, y_offset, watermark_mask=None):
        if not enabled:
            return (image,)

        mark_pil = _build_watermark_rgba(watermark, watermark_mask=watermark_mask)
        if mark_pil is None:
            return (image,)

        scale = max(0.01, float(image_scale))
        scaled_w = max(1, int(round(mark_pil.width * scale)))
        scaled_h = max(1, int(round(mark_pil.height * scale)))
        if (scaled_w, scaled_h) != mark_pil.size:
            mark_pil = mark_pil.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        mark_pil = _apply_alpha(mark_pil, alpha)

        output = []
        for sample in image:
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
                    device=image.device,
                    dtype=image.dtype,
                )
            )

        return (torch.stack(output, dim=0),)
