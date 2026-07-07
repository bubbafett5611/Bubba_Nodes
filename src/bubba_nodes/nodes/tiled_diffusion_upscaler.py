from __future__ import annotations

import math
import time

import torch
from comfy_api.latest import IO
import torch.nn.functional as F

from ..compat.core_nodes import common_ksampler, load_upscale_model, upscale_with_model
from ..compat.paths import get_filename_list
from ..compat.sampling import common_upscale, sampler_names, scheduler_names
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.progress import ProgressReporter


_PIXEL_RESIZE_METHODS = ["lanczos", "bicubic", "bilinear", "nearest-exact", "area", "bislerp"]
_REDRAW_MODES = ["linear", "chess"]
_SEAM_FIX_MODES = ["none", "band_pass", "half_tile", "half_tile_plus_intersections"]
_LANCZOS_ONLY = "Lanczos (no upscale model)"
_MAX_SEED = 0xFFFFFFFFFFFFFFFF


def _resize_image_exact(image, width, height, method):
    resized = common_upscale(image.movedim(-1, 1), width, height, method, "disabled")
    return resized.movedim(1, -1).clamp(0.0, 1.0)


def _initial_pixel_upscale(image, scale_by, resize_method, upscale_model_name):
    target_width = max(8, round(image.shape[2] * scale_by / 8) * 8)
    target_height = max(8, round(image.shape[1] * scale_by / 8) * 8)
    # Older saved workflows used bislerp here when this node upscaled latents.
    # It is not a sensible RGB resize method, so migrate it safely at runtime.
    if resize_method == "bislerp":
        resize_method = "bicubic"
    if upscale_model_name and upscale_model_name != _LANCZOS_ONLY:
        upscale_model = load_upscale_model(upscale_model_name)
        image = upscale_with_model(upscale_model, image)
    return _resize_image_exact(image, target_width, target_height, resize_method)


def _centered_crop(core, canvas_width, canvas_height, target_width, target_height):
    x1, y1, x2, y2 = core
    target_width = min(canvas_width, max(x2 - x1, target_width))
    target_height = min(canvas_height, max(y2 - y1, target_height))
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    crop_x1 = max(0, min(canvas_width - target_width, center_x - target_width // 2))
    crop_y1 = max(0, min(canvas_height - target_height, center_y - target_height // 2))
    return (crop_x1, crop_y1, crop_x1 + target_width, crop_y1 + target_height)


def _soft_rect_mask(height, width, rect, blur, device, dtype):
    x1, y1, x2, y2 = rect
    mask = torch.zeros((1, 1, height, width), device=device, dtype=dtype)
    mask[:, :, y1:y2, x1:x2] = 1.0
    if blur <= 0:
        return mask.movedim(1, -1)

    radius = max(1, math.ceil(blur * 2))
    positions = torch.arange(-radius, radius + 1, device=device, dtype=torch.float32)
    kernel = torch.exp(-(positions**2) / (2 * max(float(blur), 0.5) ** 2))
    kernel /= kernel.sum()
    working = mask.float()
    working = F.conv2d(working, kernel.view(1, 1, 1, -1), padding=(0, radius))
    working = F.conv2d(working, kernel.view(1, 1, -1, 1), padding=(radius, 0))
    return working.to(dtype=dtype).movedim(1, -1).clamp(0.0, 1.0)


def _sample_pixel_crop(crop, model, vae, positive, negative, seed, steps, cfg, sampler_name, scheduler, denoise):
    latent = {"samples": vae.encode(crop[:, :, :, :3])}
    sampled = common_ksampler(
        model,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        positive,
        negative,
        latent,
        denoise=denoise,
    )[0]
    samples = sampled["samples"]
    if getattr(samples, "is_nested", False):
        samples = samples.unbind()[0]
    decoded = vae.decode(samples)
    if len(decoded.shape) == 5:
        decoded = decoded.reshape(-1, decoded.shape[-3], decoded.shape[-2], decoded.shape[-1])
    if decoded.shape[1:3] != crop.shape[1:3]:
        decoded = _resize_image_exact(decoded, crop.shape[2], crop.shape[1], "bicubic")
    return decoded[:, :, :, :3].clamp(0.0, 1.0)


def _process_region(
    working,
    batch_index,
    core,
    context_width,
    context_height,
    mask_blur,
    model,
    vae,
    positive,
    negative,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
):
    canvas_height, canvas_width = working.shape[1:3]
    crop_box = _centered_crop(core, canvas_width, canvas_height, context_width, context_height)
    crop_x1, crop_y1, crop_x2, crop_y2 = crop_box
    crop = working[batch_index : batch_index + 1, crop_y1:crop_y2, crop_x1:crop_x2, :3]
    sampled = _sample_pixel_crop(
        crop,
        model,
        vae,
        positive,
        negative,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
    )

    x1, y1, x2, y2 = core
    local_core = (x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1)
    mask = _soft_rect_mask(crop.shape[1], crop.shape[2], local_core, mask_blur, crop.device, crop.dtype)
    composited = sampled * mask + crop * (1.0 - mask)
    working[batch_index : batch_index + 1, crop_y1:crop_y2, crop_x1:crop_x2, :3] = composited


def _grid_regions(width, height, tile_width, tile_height, mode):
    regions = [
        (x, y, min(x + tile_width, width), min(y + tile_height, height))
        for y in range(0, height, tile_height)
        for x in range(0, width, tile_width)
    ]
    if mode == "chess":
        columns = math.ceil(width / tile_width)
        regions = sorted(
            regions, key=lambda region: (((region[1] // tile_height) * columns + region[0] // tile_width) % 2, region[1], region[0])
        )
    return regions


def _seam_regions(width, height, tile_width, tile_height, seam_width, mode):
    if mode == "none" or seam_width <= 0:
        return []

    half_width = max(1, seam_width // 2)
    vertical = [
        (max(0, x - half_width), y, min(width, x + half_width), min(height, y + tile_height))
        for x in range(tile_width, width, tile_width)
        for y in range(0, height, tile_height)
    ]
    horizontal = [
        (x, max(0, y - half_width), min(width, x + tile_width), min(height, y + half_width))
        for y in range(tile_height, height, tile_height)
        for x in range(0, width, tile_width)
    ]
    if mode in ("band_pass", "half_tile"):
        return vertical + horizontal

    intersections = [
        (max(0, x - half_width), max(0, y - half_width), min(width, x + half_width), min(height, y + half_width))
        for y in range(tile_height, height, tile_height)
        for x in range(tile_width, width, tile_width)
    ]
    return vertical + horizontal + intersections


def _run_tiled_redraw(
    image,
    model,
    vae,
    positive,
    negative,
    seed,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
    tile_width,
    tile_height,
    context_padding,
    mask_blur,
    redraw_mode,
    seam_fix_mode,
    seam_fix_denoise,
    seam_fix_width,
    seam_fix_mask_blur,
    seam_fix_padding,
):
    working = image.clone()
    height, width = working.shape[1:3]
    redraw_regions = _grid_regions(width, height, tile_width, tile_height, redraw_mode)
    seam_regions = _seam_regions(width, height, tile_width, tile_height, seam_fix_width, seam_fix_mode)
    total = working.shape[0] * (len(redraw_regions) + len(seam_regions))
    progress = ProgressReporter(total)

    for batch_index in range(working.shape[0]):
        for core in redraw_regions:
            _process_region(
                working,
                batch_index,
                core,
                tile_width + context_padding * 2,
                tile_height + context_padding * 2,
                mask_blur,
                model,
                vae,
                positive,
                negative,
                seed,
                steps,
                cfg,
                sampler_name,
                scheduler,
                denoise,
            )
            progress.update(1)

        for core in seam_regions:
            _process_region(
                working,
                batch_index,
                core,
                tile_width + seam_fix_padding * 2,
                tile_height + seam_fix_padding * 2,
                seam_fix_mask_blur,
                model,
                vae,
                positive,
                negative,
                seed,
                steps,
                cfg,
                sampler_name,
                scheduler,
                seam_fix_denoise,
            )
            progress.update(1)

    return working.clamp(0.0, 1.0), total


class BubbaTiledDiffusionUpscaler(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        upscale_models = [_LANCZOS_ONLY, *get_filename_list("upscale_models")]
        i, f = IO.Int.Input, IO.Float.Input
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        inputs = [
            i("seed", default=0, min=0, max=_MAX_SEED, control_after_generate=True),
            i("steps", default=20, min=1, max=10000),
            f("cfg", default=6.0, min=0, max=100, step=0.1, round=0.01),
            IO.Combo.Input("sampler_name", options=sampler_names()),
            IO.Combo.Input("scheduler", options=scheduler_names()),
            f("denoise", default=0.2, min=0, max=1, step=0.01),
            i("tile_width", default=512, min=128, max=4096, step=64),
            i("tile_height", default=512, min=128, max=4096, step=64),
            f("scale_by", default=2, min=1, max=8, step=0.05),
            i("overlap", default=32, min=0, max=1024, step=8),
            IO.Combo.Input("resize_method", options=_PIXEL_RESIZE_METHODS),
            i("mask_blur", default=8, min=0, max=64),
            IO.Combo.Input("redraw_mode", options=_REDRAW_MODES),
            IO.Combo.Input("seam_fix_mode", options=_SEAM_FIX_MODES),
            f("seam_fix_denoise", default=0.15, min=0, max=1, step=0.01),
            i("seam_fix_width", default=64, min=0, max=1024, step=8),
            i("seam_fix_mask_blur", default=8, min=0, max=64),
            i("seam_fix_padding", default=32, min=0, max=1024, step=8),
            IO.Combo.Input("upscale_model_name", options=upscale_models),
            pipe.Input("pipe", optional=True),
            IO.Image.Input("image", optional=True),
            IO.Latent.Input("latent", optional=True),
            metadata.Input("metadata", optional=True),
            IO.Model.Input("model", optional=True),
            IO.Vae.Input("vae", optional=True),
            IO.Conditioning.Input("positive", optional=True),
            IO.Conditioning.Input("negative", optional=True),
        ]
        return IO.Schema(
            node_id="BubbaTiledDiffusionUpscaler",
            display_name="Bubba Tiled KSampler Upscaler (Seam Fix)",
            category="Bubba Nodes/Image",
            description="Pixel-upscales then samples contextual tiles with optional seam repair.",
            inputs=inputs,
            outputs=[
                pipe.Output("pipe"),
                IO.Image.Output("image"),
                IO.Latent.Output("latent"),
                metadata.Output("metadata"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(
        cls,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        tile_width,
        tile_height,
        scale_by,
        overlap,
        resize_method,
        mask_blur=8,
        redraw_mode="linear",
        seam_fix_mode="none",
        seam_fix_denoise=0.15,
        seam_fix_width=64,
        seam_fix_mask_blur=8,
        seam_fix_padding=32,
        upscale_model_name=_LANCZOS_ONLY,
        pipe=None,
        image=None,
        latent=None,
        metadata=None,
        model=None,
        vae=None,
        positive=None,
        negative=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_model = resolve_pipe_value(model, source_pipe.model, "model")
        resolved_vae = resolve_pipe_value(vae, source_pipe.vae, "vae")
        resolved_positive = resolve_pipe_value(positive, source_pipe.positive, "positive conditioning")
        resolved_negative = resolve_pipe_value(negative, source_pipe.negative, "negative conditioning")

        if image is not None:
            source_image = image
        elif source_pipe.image is not None:
            source_image = source_pipe.image
        else:
            source_latent = latent if latent is not None else source_pipe.latent
            source_latent = resolve_pipe_value(source_latent, None, "image or latent")
            samples = source_latent["samples"]
            if getattr(samples, "is_nested", False):
                samples = samples.unbind()[0]
            source_image = resolved_vae.decode(samples)
            if len(source_image.shape) == 5:
                source_image = source_image.reshape(-1, source_image.shape[-3], source_image.shape[-2], source_image.shape[-1])

        start_time = time.perf_counter()
        initial = _initial_pixel_upscale(source_image[:, :, :, :3], scale_by, resize_method, upscale_model_name)
        upscaled, tile_count = _run_tiled_redraw(
            initial,
            resolved_model,
            resolved_vae,
            resolved_positive,
            resolved_negative,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
            tile_width,
            tile_height,
            overlap,
            mask_blur,
            redraw_mode,
            seam_fix_mode,
            seam_fix_denoise,
            seam_fix_width,
            seam_fix_mask_blur,
            seam_fix_padding,
        )
        final_latent = {"samples": resolved_vae.encode(upscaled[:, :, :, :3])}
        elapsed = time.perf_counter() - start_time
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            sampler_time_seconds=elapsed,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
        )
        updated_pipe = source_pipe.updated(
            image=upscaled,
            latent=final_latent,
            metadata=updated_metadata,
            model=resolved_model,
            vae=resolved_vae,
            positive=resolved_positive,
            negative=resolved_negative,
        )
        info = (
            f"Tiles/passes: {tile_count}  Output: {upscaled.shape[2]}x{upscaled.shape[1]}  "
            f"Context: {overlap}px  Seam fix: {seam_fix_mode}  Time: {elapsed:.3f}s"
        )
        return IO.NodeOutput(updated_pipe, upscaled, final_latent, updated_metadata, info)
