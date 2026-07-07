from __future__ import annotations

import logging

from .paths import get_filename_list


logger = logging.getLogger("bubba_nodes")


def _nodes():
    try:
        import nodes  # type: ignore

        return nodes
    except Exception as error:  # pragma: no cover - only hit in broken Comfy runtime
        raise RuntimeError("Bubba Nodes requires ComfyUI core nodes for this operation.") from error


def checkpoint_names() -> list[str]:
    return get_filename_list("checkpoints")


def load_checkpoint(ckpt_name: str):
    loader = _nodes().CheckpointLoaderSimple()
    try:
        return loader.load_checkpoint(ckpt_name)
    except AttributeError as error:
        if "'NoneType' object has no attribute 'is_dynamic'" not in str(error):
            raise

        removed = _prune_dead_model_cache_entries()
        if not removed:
            raise

        logger.warning(
            "Removed %d stale ComfyUI model-cache entr%s after a failed checkpoint load; retrying once.",
            removed,
            "y" if removed == 1 else "ies",
        )
        return loader.load_checkpoint(ckpt_name)


def _prune_dead_model_cache_entries() -> int:
    """Remove entries whose weakly referenced model patcher has disappeared.

    Some ComfyUI releases leave these entries behind after interruption or model
    unloading, then dereference ``entry.model`` inside ``free_memory``.
    """
    try:
        from comfy import model_management  # type: ignore
    except Exception:
        return 0

    loaded_models = getattr(model_management, "current_loaded_models", None)
    if not isinstance(loaded_models, list):
        return 0

    stale_indices = [index for index, entry in enumerate(loaded_models) if getattr(entry, "model", None) is None]
    for index in reversed(stale_indices):
        loaded_models.pop(index)
    return len(stale_indices)


def vae_names() -> list[str]:
    nodes = _nodes()
    try:
        return list(nodes.VAELoader.vae_list(nodes.VAELoader))
    except Exception:
        return get_filename_list("vae")


def load_vae(vae_name: str):
    return _nodes().VAELoader().load_vae(vae_name)[0]


def load_clip(clip_name: str, clip_type: str, device: str = "default"):
    return _nodes().CLIPLoader().load_clip(clip_name, type=clip_type, device=device)[0]


class LoraApplier:
    def __init__(self) -> None:
        self._loader = _nodes().LoraLoader()

    def apply(self, model, clip, lora_name: str, strength_model: float, strength_clip: float):
        return self._loader.load_lora(model, clip, lora_name, strength_model, strength_clip)


def common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent, *, denoise=1.0):
    return _nodes().common_ksampler(
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
    )


def encode_inpaint_conditioning(positive, negative, pixels, vae, mask, noise_mask: bool = True):
    return _nodes().InpaintModelConditioning().encode(positive, negative, pixels, vae, mask, noise_mask)


def multiply_conditioning(conditioning, multiplier: float):
    return _nodes().ConditioningMultiply().multiply(conditioning, multiplier)[0]


def load_upscale_model(upscale_model_name: str):
    from comfy_extras.nodes_upscale_model import UpscaleModelLoader  # type: ignore

    if hasattr(UpscaleModelLoader, "execute"):
        return UpscaleModelLoader.execute(upscale_model_name)[0]
    loader = UpscaleModelLoader()
    if hasattr(loader, "load_model"):
        return loader.load_model(upscale_model_name)[0]
    return loader.execute(upscale_model_name)[0]


def upscale_with_model(upscale_model, image):
    from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel  # type: ignore

    if hasattr(ImageUpscaleWithModel, "execute"):
        return ImageUpscaleWithModel.execute(upscale_model, image)[0]
    node = ImageUpscaleWithModel()
    if hasattr(node, "upscale"):
        return node.upscale(upscale_model, image)[0]
    return node.execute(upscale_model, image)[0]
