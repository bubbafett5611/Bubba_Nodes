from __future__ import annotations

from typing import Any

from .paths import get_folder_paths


def load_torch_file(path: str):
    try:
        import comfy.utils  # type: ignore
    except Exception as error:  # pragma: no cover - only hit in broken Comfy runtime
        raise RuntimeError("Bubba checkpoint merging requires ComfyUI's checkpoint file loader.") from error
    return comfy.utils.load_torch_file(str(path), safe_load=True, return_metadata=True)


def save_torch_file(state_dict: dict[str, Any], path: str, metadata: dict[str, str]) -> None:
    try:
        import comfy.utils  # type: ignore
    except Exception as error:  # pragma: no cover - only hit in broken Comfy runtime
        raise RuntimeError("Bubba checkpoint merging requires ComfyUI's checkpoint file saver.") from error
    comfy.utils.save_torch_file(state_dict, str(path), metadata=metadata)


def load_state_dict_guess_config(state_dict: dict[str, Any], metadata: dict[str, str] | None = None):
    try:
        import comfy.sd  # type: ignore
    except Exception as error:  # pragma: no cover - only hit in broken Comfy runtime
        raise RuntimeError("Bubba checkpoint merging requires ComfyUI's checkpoint object loader.") from error
    return comfy.sd.load_state_dict_guess_config(
        dict(state_dict),
        output_vae=True,
        output_clip=True,
        output_clipvision=False,
        embedding_directory=[str(path) for path in get_folder_paths("embeddings")],
        output_model=True,
        metadata=metadata or {},
    )
