from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from ..compat.paths import get_folder_paths


_DETECTOR_CACHE_MAX_SIZE = 2
_DETECTOR_CACHE: OrderedDict[tuple[str, float], Any] = OrderedDict()
_NO_MODELS_SENTINEL = "No ultralytics models found"


def _ultralytics_roots_from_folder_paths() -> list[Path]:
    roots: list[Path] = []

    roots.extend(Path(path) / "ultralytics" for path in get_folder_paths("models"))

    for model_type in ("ultralytics", "ultralytics_bbox", "ultralytics_segm"):
        for raw_path in get_folder_paths(model_type):
            path = Path(raw_path)
            path_name = path.name.lower()
            if path_name in {"bbox", "segm"}:
                path = path.parent
            roots.append(path if path.name.lower() == "ultralytics" else path / "ultralytics")

    unique_roots: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique_roots.append(root)
    return unique_roots


def ultralytics_roots(root: str | Path | None = None) -> list[Path]:
    if root is not None:
        return [Path(root)]
    return _ultralytics_roots_from_folder_paths()


def ultralytics_root(root: str | Path | None = None) -> Path:
    roots = ultralytics_roots(root)
    if not roots:
        raise RuntimeError("Unable to resolve any ComfyUI ultralytics model folders.")
    return roots[0]


def discover_detector_models(root: str | Path | None = None) -> list[str]:
    names: set[str] = set()
    for base in ultralytics_roots(root):
        for mode in ("bbox", "segm"):
            mode_dir = _child_dir_case_insensitive(base, mode)
            if not mode_dir.is_dir():
                continue
            names.update(f"{mode}/{path.name}" for path in mode_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pt")
    return sorted(names)


def detector_dropdown_values(root: str | Path | None = None) -> list[str]:
    try:
        values = discover_detector_models(root)
    except Exception:
        values = []
    return values or [_NO_MODELS_SENTINEL]


def resolve_detector_model_path(model_name: str, root: str | Path | None = None) -> tuple[str, Path]:
    normalized = str(model_name or "").replace("\\", "/").strip()
    if normalized == _NO_MODELS_SENTINEL:
        raise ValueError(
            "No ultralytics detector models were found in ComfyUI's models/ultralytics/bbox or models/ultralytics/segm folders."
        )

    if "/" not in normalized:
        raise ValueError(f"Invalid detector model selection '{model_name}'. Expected a value like 'bbox/model.pt' or 'segm/model.pt'.")

    mode, filename = normalized.split("/", 1)
    if mode not in {"bbox", "segm"}:
        raise ValueError(f"Invalid detector model mode '{mode}'. Expected 'bbox' or 'segm'.")

    if not filename or Path(filename).name != filename or Path(filename).suffix.lower() != ".pt":
        raise ValueError(f"Invalid detector model filename '{filename}'. Expected a .pt file in the selected detector folder.")

    checked_paths = []
    for base in ultralytics_roots(root):
        mode_dir = _child_dir_case_insensitive(base, mode)
        path = mode_dir / filename
        checked_paths.append(str(path))
        if path.is_file():
            return mode, path
    raise FileNotFoundError(f"Detector model '{normalized}' was not found. Checked: {', '.join(checked_paths)}")


def _child_dir_case_insensitive(parent: Path, child_name: str) -> Path:
    direct = parent / child_name
    if direct.exists():
        return direct
    if parent.is_dir():
        target = child_name.lower()
        for child in parent.iterdir():
            if child.is_dir() and child.name.lower() == target:
                return child
    return direct


def load_detector(model_name: str, root: str | Path | None = None):
    mode, path = resolve_detector_model_path(model_name, root)
    stat = path.stat()
    cache_key = (str(path.resolve()), stat.st_mtime)
    if cache_key in _DETECTOR_CACHE:
        _DETECTOR_CACHE.move_to_end(cache_key)
    else:
        try:
            from ultralytics import YOLO
        except Exception as error:
            raise RuntimeError(
                "BubbaDetailer requires ultralytics to load detector models. "
                "Install it in the ComfyUI Python environment, then restart ComfyUI."
            ) from error
        _DETECTOR_CACHE[cache_key] = YOLO(str(path))
        while len(_DETECTOR_CACHE) > _DETECTOR_CACHE_MAX_SIZE:
            _DETECTOR_CACHE.popitem(last=False)
    return mode, path, _DETECTOR_CACHE[cache_key]


def clear_detector_cache() -> None:
    _DETECTOR_CACHE.clear()
