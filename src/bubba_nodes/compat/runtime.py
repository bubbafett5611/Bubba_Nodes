from __future__ import annotations

import torch


def pillow_call(func, *args):
    try:
        import node_helpers  # type: ignore
    except Exception:
        return func(*args)
    if hasattr(node_helpers, "pillow"):
        return node_helpers.pillow(func, *args)
    return func(*args)


def intermediate_dtype():
    try:
        import comfy.model_management  # type: ignore

        if hasattr(comfy.model_management, "intermediate_dtype"):
            return comfy.model_management.intermediate_dtype()
    except Exception:
        pass
    return torch.float32


def intermediate_device():
    try:
        import comfy.model_management  # type: ignore

        if hasattr(comfy.model_management, "intermediate_device"):
            return comfy.model_management.intermediate_device()
    except Exception:
        pass
    return "cpu"
