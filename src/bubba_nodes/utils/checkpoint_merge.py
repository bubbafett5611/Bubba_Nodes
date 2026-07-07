from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..compat.checkpoint_io import load_state_dict_guess_config, load_torch_file, save_torch_file
from ..compat.paths import get_filename_list, get_folder_paths, get_full_path_or_raise
from .checkpointing import checkpoint_display_name, checkpoint_sha256, checkpoint_short_hash


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\-/]+")


def checkpoint_choices() -> list[str]:
    return get_filename_list("checkpoints")


def checkpoint_path(ckpt_name: str) -> Path:
    return Path(get_full_path_or_raise("checkpoints", ckpt_name))


def checkpoint_root() -> Path:
    paths = get_folder_paths("checkpoints")
    if not paths:
        raise RuntimeError("No ComfyUI checkpoint folder is configured.")
    return Path(paths[0])


def sanitize_checkpoint_prefix(value: str, fallback: str = "bubba_merge") -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/")
    text = _SAFE_FILENAME_RE.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("._-/")
    return text or fallback


def ensure_safetensors_name(value: str) -> str:
    text = sanitize_checkpoint_prefix(value)
    if text.lower().endswith((".safetensors", ".sft")):
        return text
    if "." in Path(text).name:
        text = str(Path(text).with_suffix(""))
    return f"{text}.safetensors"


def resolve_checkpoint_save_path(filename_prefix: str, overwrite: bool) -> tuple[Path, str]:
    relative_name = ensure_safetensors_name(filename_prefix)
    root = checkpoint_root().resolve()
    target = (root / relative_name).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Checkpoint save path must stay inside the ComfyUI checkpoints folder.")
    target.parent.mkdir(parents=True, exist_ok=True)

    if overwrite or not target.exists():
        return target, str(target.relative_to(root)).replace("\\", "/")

    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    for index in range(1, 10000):
        candidate = parent / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate, str(candidate.relative_to(root)).replace("\\", "/")
    raise FileExistsError(f"Could not find available filename for {relative_name!r}.")


def load_checkpoint_state_dict(ckpt_name: str) -> tuple[dict[str, Any], dict[str, str]]:
    path = checkpoint_path(ckpt_name)
    state_dict, metadata = load_torch_file(str(path))
    if not isinstance(state_dict, dict):
        raise ValueError(f"Checkpoint {ckpt_name!r} did not load as a state dict.")
    return state_dict, {str(k): str(v) for k, v in dict(metadata or {}).items()}


def load_merged_checkpoint_objects(state_dict: dict[str, Any], metadata: dict[str, str] | None = None):
    # Comfy's checkpoint loading path mutates the state dict while it builds the
    # live MODEL/CLIP/VAE objects. Keep the merge payload intact so it can still
    # be saved afterward.
    model, clip, vae, _clipvision = load_state_dict_guess_config(state_dict, metadata)
    return model, clip, vae


def is_mergeable_tensor(left: Any, right: Any) -> bool:
    import torch

    return (
        isinstance(left, torch.Tensor)
        and isinstance(right, torch.Tensor)
        and left.shape == right.shape
        and left.is_floating_point()
        and right.is_floating_point()
    )


def blend_tensors(left: Any, right: Any, ratio: float) -> Any:
    import torch

    output_dtype = left.dtype
    left_float = left.detach().to(device="cpu", dtype=torch.float32)
    right_float = right.detach().to(device="cpu", dtype=torch.float32)
    merged = left_float.mul(1.0 - ratio).add(right_float, alpha=ratio)
    return merged.to(dtype=output_dtype).contiguous()


def diff_add_tensors(base: Any, add: Any, subtract: Any, strength: float) -> Any:
    import torch

    output_dtype = base.dtype
    base_float = base.detach().to(device="cpu", dtype=torch.float32)
    add_float = add.detach().to(device="cpu", dtype=torch.float32)
    subtract_float = subtract.detach().to(device="cpu", dtype=torch.float32)
    merged = base_float.add(add_float.sub(subtract_float), alpha=strength)
    return merged.to(dtype=output_dtype).contiguous()


def binary_merge_state_dict(sd_a: dict[str, Any], sd_b: dict[str, Any], ratio: float) -> tuple[dict[str, Any], dict[str, int]]:
    merged: dict[str, Any] = {}
    stats = {
        "source_a_keys": len(sd_a),
        "source_b_keys": len(sd_b),
        "merged_tensors": 0,
        "carried_a_keys": 0,
        "shape_mismatch_keys": 0,
        "b_only_keys": 0,
    }

    for key, value_a in sd_a.items():
        if key not in sd_b:
            merged[key] = value_a
            stats["carried_a_keys"] += 1
            continue
        value_b = sd_b[key]
        if is_mergeable_tensor(value_a, value_b):
            merged[key] = blend_tensors(value_a, value_b, ratio)
            stats["merged_tensors"] += 1
            continue
        merged[key] = value_a
        stats["shape_mismatch_keys"] += 1

    stats["b_only_keys"] = len(set(sd_b) - set(sd_a))
    return merged, stats


def triple_merge_state_dict(
    sd_a: dict[str, Any],
    sd_b: dict[str, Any],
    sd_c: dict[str, Any],
    strength: float,
) -> tuple[dict[str, Any], dict[str, int]]:
    merged: dict[str, Any] = {}
    stats = {
        "source_a_keys": len(sd_a),
        "source_b_keys": len(sd_b),
        "source_c_keys": len(sd_c),
        "merged_tensors": 0,
        "carried_a_keys": 0,
        "shape_mismatch_keys": 0,
    }

    for key, value_a in sd_a.items():
        value_b = sd_b.get(key)
        value_c = sd_c.get(key)
        if is_mergeable_tensor(value_a, value_b) and is_mergeable_tensor(value_a, value_c):
            merged[key] = diff_add_tensors(value_a, value_b, value_c, strength)
            stats["merged_tensors"] += 1
            continue
        merged[key] = value_a
        if key in sd_b or key in sd_c:
            stats["shape_mismatch_keys"] += 1
        else:
            stats["carried_a_keys"] += 1

    return merged, stats


def recipe_metadata(recipe: dict[str, Any]) -> dict[str, str]:
    return {
        "bubba_merge_recipe": json.dumps(recipe, ensure_ascii=False, sort_keys=True),
        "bubba_merge_created_at": datetime.now().isoformat(timespec="seconds"),
    }


def recipe_text(recipe: dict[str, Any], pretty: bool = True) -> str:
    return json.dumps(recipe, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)


def checkpoint_fingerprint(ckpt_name: str) -> dict[str, Any]:
    path = checkpoint_path(ckpt_name)
    stat = path.stat()
    return {
        "checkpoint_name": str(ckpt_name),
        "display_name": checkpoint_display_name(ckpt_name),
        "path": str(path),
        "sha256": checkpoint_sha256(path),
        "short_hash": checkpoint_short_hash(path),
        "file_size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def save_checkpoint_merge(state_dict: dict[str, Any], filename_prefix: str, metadata: dict[str, str], overwrite: bool) -> tuple[Path, str]:
    if not state_dict:
        raise ValueError("Refusing to save an empty checkpoint merge payload. Re-run the merge node with the updated Bubba Nodes code.")

    target, relative_name = resolve_checkpoint_save_path(filename_prefix, overwrite=overwrite)
    save_torch_file(state_dict, str(target), metadata)
    return target, relative_name
