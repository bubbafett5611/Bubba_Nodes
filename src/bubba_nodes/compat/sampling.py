from __future__ import annotations


def _comfy_samplers():
    try:
        import comfy.samplers  # type: ignore

        return comfy.samplers
    except Exception:
        return None


def sampler_names() -> list[str]:
    samplers = _comfy_samplers()
    if samplers is None:
        return []
    return list(getattr(samplers.KSampler, "SAMPLERS", []))


def scheduler_names() -> list[str]:
    samplers = _comfy_samplers()
    if samplers is None:
        return []
    return list(getattr(samplers.KSampler, "SCHEDULERS", []))


def common_upscale(image, width: int, height: int, method: str, crop: str):
    try:
        import comfy.utils  # type: ignore
    except Exception as error:  # pragma: no cover - only hit in broken Comfy runtime
        raise RuntimeError("Bubba Nodes requires ComfyUI's common_upscale helper for this operation.") from error
    return comfy.utils.common_upscale(image, width, height, method, crop)
