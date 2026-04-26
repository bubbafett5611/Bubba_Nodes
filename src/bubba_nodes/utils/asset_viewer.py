from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import json
import os
import re
import struct
from typing import Any

try:
    from PIL import Image
except Exception:  # pragma: no cover - Pillow is expected in Comfy runtime but keep fallback.
    Image = None


ALLOWED_UPLOAD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


@dataclass(frozen=True)
class AssetRoot:
    key: str
    label: str
    path: str


def _safe_real_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _is_path_within_root(path: str, root: str) -> bool:
    path_real = _safe_real_path(path)
    root_real = _safe_real_path(root)
    try:
        return os.path.commonpath([path_real, root_real]) == root_real
    except ValueError:
        return False


def _sanitize_text(value: Any, max_len: int = 600) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _safe_json_dumps(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return "{}"


def _parse_json_text(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _resolve_prompt_ref(prompt_graph: dict[str, Any], ref: Any) -> dict[str, Any] | None:
    if not isinstance(ref, (list, tuple)) or not ref:
        return None

    node_id = str(ref[0])
    node = prompt_graph.get(node_id)
    if isinstance(node, dict):
        return node
    return None


def _extract_text_from_ref(prompt_graph: dict[str, Any], ref: Any) -> str:
    node = _resolve_prompt_ref(prompt_graph, ref)
    if not node:
        return ""
    if str(node.get("class_type") or "") != "CLIPTextEncode":
        return ""
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
    return _sanitize_text(inputs.get("text", ""), max_len=6000)


def _extract_model_name_from_ref(prompt_graph: dict[str, Any], ref: Any) -> str:
    node = _resolve_prompt_ref(prompt_graph, ref)
    if not node:
        return ""

    class_type = str(node.get("class_type") or "")
    inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}

    if class_type in {"CheckpointLoaderSimple", "CheckpointLoader"}:
        return _sanitize_text(inputs.get("ckpt_name", ""), max_len=500)
    if class_type == "UNETLoader":
        return _sanitize_text(inputs.get("unet_name", ""), max_len=500)
    return ""


def _extract_generation_from_comfy_prompt(prompt_graph: Any) -> dict[str, Any]:
    if not isinstance(prompt_graph, dict):
        return {}

    sampler_node: dict[str, Any] | None = None
    for node in prompt_graph.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        if class_type in {"KSampler", "KSamplerAdvanced"}:
            sampler_node = node
            break

    if sampler_node is None:
        return {}

    inputs = sampler_node.get("inputs") if isinstance(sampler_node.get("inputs"), dict) else {}
    generation: dict[str, Any] = {}

    field_map = {
        "seed": "seed",
        "steps": "steps",
        "cfg": "cfg",
        "sampler_name": "sampler_name",
        "scheduler": "scheduler",
        "denoise": "denoise",
    }
    for target_key, source_key in field_map.items():
        if source_key in inputs and inputs[source_key] not in (None, ""):
            generation[target_key] = inputs[source_key]

    model_name = _extract_model_name_from_ref(prompt_graph, inputs.get("model"))
    if model_name:
        generation["model_name"] = model_name

    positive_prompt = _extract_text_from_ref(prompt_graph, inputs.get("positive"))
    if positive_prompt:
        generation["positive_prompt"] = positive_prompt

    negative_prompt = _extract_text_from_ref(prompt_graph, inputs.get("negative"))
    if negative_prompt:
        generation["negative_prompt"] = negative_prompt

    return generation


def _extract_generation_from_a1111_parameters(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str):
        return {}

    text = raw.strip()
    if not text:
        return {}

    fields: dict[str, str] = {}
    patterns = {
        "steps": r"\bSteps:\s*([^,\n]+)",
        "sampler_name": r"\bSampler:\s*([^,\n]+)",
        "cfg": r"\bCFG scale:\s*([^,\n]+)",
        "seed": r"\bSeed:\s*([^,\n]+)",
        "model_name": r"\bModel(?: hash|):\s*([^,\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            fields[key] = _sanitize_text(match.group(1), max_len=400)

    # Heuristic split for prompt/negative sections in common parameter dumps.
    if "Negative prompt:" in text:
        before, after = text.split("Negative prompt:", 1)
        positive = before.split("\n", 1)[0].strip()
        negative = after.split("\n", 1)[0].strip()
        if positive:
            fields["positive_prompt"] = _sanitize_text(positive, max_len=6000)
        if negative:
            fields["negative_prompt"] = _sanitize_text(negative, max_len=6000)

    return fields


def _extract_generation_from_png_info(info: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(info, dict):
        return {}

    prompt_payload = _parse_json_text(info.get("prompt"))
    from_prompt = _extract_generation_from_comfy_prompt(prompt_payload)
    if from_prompt:
        return from_prompt

    return _extract_generation_from_a1111_parameters(info.get("parameters"))


def _parse_safetensors_header(path: str, max_header_bytes: int = 4 * 1024 * 1024) -> dict[str, Any]:
    try:
        with open(path, "rb") as handle:
            raw_len = handle.read(8)
            if len(raw_len) != 8:
                return {}
            header_len = struct.unpack("<Q", raw_len)[0]
            if header_len <= 0 or header_len > max_header_bytes:
                return {}
            header_bytes = handle.read(int(header_len))
            if len(header_bytes) != int(header_len):
                return {}
            payload = json.loads(header_bytes.decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                return {}
            metadata = payload.get("__metadata__", {})
            return metadata if isinstance(metadata, dict) else {}
    except Exception:
        return {}


def _parse_png_metadata(path: str) -> dict[str, Any]:
    if Image is None:
        return {}

    try:
        with Image.open(path) as img:
            info = getattr(img, "info", {}) or {}
    except Exception:
        return {}

    if not isinstance(info, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for key, value in info.items():
        normalized_key = str(key)
        if normalized_key == "bubba_metadata" and isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                cleaned[normalized_key] = {
                    str(meta_key): _sanitize_text(meta_value, max_len=2000) for meta_key, meta_value in parsed.items()
                }
                continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[normalized_key] = _sanitize_text(value)
        elif isinstance(value, dict):
            cleaned[normalized_key] = _safe_json_dumps(value)

    generation = _extract_generation_from_png_info(info)
    if generation:
        cleaned["generation"] = generation
    return cleaned


def _flatten_to_search_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.append(_flatten_to_search_text(item))
        return " ".join(parts)
    if isinstance(value, list):
        return " ".join(_flatten_to_search_text(item) for item in value)
    return str(value)


def summarize_metadata(extension: str, path: str) -> dict[str, Any]:
    ext = extension.lower()
    if ext == ".safetensors":
        metadata = _parse_safetensors_header(path)
        summary = {
            "format": "safetensors",
            "keys": sorted([str(k) for k in metadata.keys()]),
        }
        if metadata:
            summary["metadata"] = {str(k): _sanitize_text(v, max_len=800) for k, v in metadata.items()}
        return summary

    if ext == ".png":
        metadata = _parse_png_metadata(path)
        summary = {
            "format": "png",
            "keys": sorted([str(k) for k in metadata.keys()]),
        }
        if metadata:
            summary["metadata"] = metadata
        return summary

    return {}


def discover_asset_roots() -> list[AssetRoot]:
    roots: list[AssetRoot] = []
    seen: set[str] = set()

    try:
        import folder_paths  # type: ignore
    except Exception:
        folder_paths = None

    if folder_paths is not None:
        for key, label, getter_name in [
            ("input", "Comfy Input", "get_input_directory"),
            ("output", "Comfy Output", "get_output_directory"),
        ]:
            try:
                getter = getattr(folder_paths, getter_name)
                folder = getter()
            except Exception:
                folder = None
            if not folder:
                continue
            real = _safe_real_path(folder)
            if real in seen or not os.path.isdir(folder):
                continue
            seen.add(real)
            roots.append(AssetRoot(key=key, label=label, path=os.path.abspath(folder)))

    if not roots:
        fallback = os.getcwd()
        roots.append(AssetRoot(key="cwd", label="Current Directory", path=os.path.abspath(fallback)))

    return roots


def resolve_requested_root(requested_root: str | None, allowed_roots: list[AssetRoot]) -> str:
    if not allowed_roots:
        raise ValueError("No asset roots available.")

    if not requested_root:
        return allowed_roots[0].path

    requested = requested_root.strip()
    if not requested:
        return allowed_roots[0].path

    root_by_path = {os.path.abspath(root.path): root for root in allowed_roots}
    requested_abs = os.path.abspath(requested)
    if requested_abs in root_by_path:
        return requested_abs

    for root in allowed_roots:
        if requested == root.key:
            return root.path

    raise ValueError("Requested root is not allowed.")


def resolve_requested_file(requested_path: str | None, allowed_roots: list[AssetRoot]) -> str:
    if not allowed_roots:
        raise ValueError("No asset roots available.")

    raw = str(requested_path or "").strip()
    if not raw:
        raise ValueError("Missing file path.")

    normalized = os.path.abspath(raw)
    if not os.path.isfile(normalized):
        raise FileNotFoundError("File does not exist.")

    for root in allowed_roots:
        if _is_path_within_root(normalized, root.path):
            return normalized

    raise PermissionError("Requested file is outside allowed roots.")


def find_root_for_path(path: str, allowed_roots: list[AssetRoot]) -> AssetRoot | None:
    normalized = os.path.abspath(path)
    for root in allowed_roots:
        if _is_path_within_root(normalized, root.path):
            return root
    return None


def sanitize_upload_filename(filename: str, fallback: str = "upload.png") -> str:
    raw_name = os.path.basename(str(filename or "").strip())
    raw_name = raw_name.replace("\x00", "")
    raw_name = raw_name.replace("/", "_").replace("\\", "_")
    raw_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name)

    if not raw_name or raw_name in {".", ".."}:
        raw_name = fallback

    stem = Path(raw_name).stem or "upload"
    ext = Path(raw_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_IMAGE_EXTENSIONS:
        ext = ".png"

    safe = f"{stem}{ext}"
    if len(safe) <= 180:
        return safe

    trimmed_stem = stem[: max(1, 180 - len(ext))]
    return f"{trimmed_stem}{ext}"


def make_unique_destination_path(root: str, filename: str) -> str:
    normalized_root = os.path.abspath(root)
    safe_name = sanitize_upload_filename(filename)
    base_stem = Path(safe_name).stem
    base_ext = Path(safe_name).suffix.lower()

    candidate = os.path.join(normalized_root, safe_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(normalized_root, f"{base_stem}_{counter}{base_ext}")
        counter += 1

    return candidate


def build_asset_item(path: str, root: str, include_metadata: bool = False) -> dict[str, Any]:
    normalized_root = os.path.abspath(root)
    abs_path = os.path.abspath(path)
    if not _is_path_within_root(abs_path, normalized_root):
        raise PermissionError("Requested file is outside selected root.")

    extension = Path(abs_path).suffix.lower()
    rel_path = os.path.relpath(abs_path, normalized_root)
    stat = os.stat(abs_path)

    item: dict[str, Any] = {
        "name": os.path.basename(abs_path),
        "path": abs_path,
        "relative_path": rel_path,
        "extension": extension,
        "size_bytes": int(stat.st_size),
        "modified_ts": float(stat.st_mtime),
    }

    if include_metadata and extension in {".safetensors", ".png"}:
        metadata = summarize_metadata(extension, abs_path)
        if metadata:
            item["metadata"] = metadata

    return item


def generate_thumbnail_bytes(path: str, max_size: int = 256) -> bytes | None:
    if Image is None:
        return None

    try:
        size = max(32, min(int(max_size), 1024))
    except Exception:
        size = 256

    try:
        with Image.open(path) as img:
            image = img.convert("RGBA")
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
    except Exception:
        return None


def scan_assets(
    root: str,
    query: str = "",
    extensions: list[str] | None = None,
    limit: int = 600,
    include_metadata: bool = True,
    offset: int = 0,
    search_in_metadata: bool = True,
    sort_by: str = "name",
    sort_dir: str = "asc",
    min_size_bytes: int | None = None,
    max_size_bytes: int | None = None,
    modified_after_ts: float | None = None,
    metadata_mode: str = "all",
) -> list[dict[str, Any]]:
    normalized_root = os.path.abspath(root)
    requested_exts = [ext.lower() for ext in (extensions or []) if ext.strip()]
    requested_exts = [ext if ext.startswith(".") else f".{ext}" for ext in requested_exts]

    if not os.path.isdir(normalized_root):
        return []

    q = query.strip().lower()
    limit = max(1, min(int(limit), 3000))
    offset = max(0, int(offset))

    requested_sort_by = str(sort_by or "name").strip().lower()
    if requested_sort_by not in {"name", "modified", "size", "metadata"}:
        requested_sort_by = "name"

    requested_sort_dir = str(sort_dir or "asc").strip().lower()
    if requested_sort_dir not in {"asc", "desc"}:
        requested_sort_dir = "asc"

    requested_metadata_mode = str(metadata_mode or "all").strip().lower()
    _valid_metadata_modes = {
        "all",
        "has_generation",
        "missing_generation",
        "has_bubba_metadata",
        "missing_bubba_metadata",
        "has_workflow",
        "missing_workflow",
    }
    if requested_metadata_mode not in _valid_metadata_modes:
        requested_metadata_mode = "all"

    min_size = int(min_size_bytes) if isinstance(min_size_bytes, int) else None
    if min_size is not None and min_size < 0:
        min_size = 0

    max_size = int(max_size_bytes) if isinstance(max_size_bytes, int) else None
    if max_size is not None and max_size < 0:
        max_size = None

    modified_after = float(modified_after_ts) if isinstance(modified_after_ts, (int, float)) else None

    # Fast path keeps streaming behavior for default sort.
    stream_fast_path = requested_sort_by == "name" and requested_sort_dir == "asc"

    files: list[dict[str, Any]] = []
    matched = 0

    for current_dir, dirnames, filenames in os.walk(normalized_root):
        dirnames.sort(key=str.lower)
        filenames.sort(key=str.lower)
        for filename in filenames:
            extension = Path(filename).suffix.lower()
            if requested_exts and extension not in requested_exts:
                continue

            abs_path = os.path.join(current_dir, filename)
            if not _is_path_within_root(abs_path, normalized_root):
                continue

            rel_path = os.path.relpath(abs_path, normalized_root)
            metadata_summary: dict[str, Any] = {}
            supports_metadata = extension in {".safetensors", ".png"}
            base_search_blob = f"{filename} {rel_path}".lower()

            needs_metadata_for_query = bool(q and search_in_metadata and supports_metadata and q not in base_search_blob)
            needs_metadata_for_payload = bool(include_metadata and supports_metadata)
            if needs_metadata_for_query or needs_metadata_for_payload:
                metadata_summary = summarize_metadata(extension, abs_path)

            if q:
                if q not in base_search_blob:
                    if not metadata_summary:
                        continue
                    metadata_blob = _flatten_to_search_text(metadata_summary).lower()
                    if q not in metadata_blob:
                        continue

            try:
                stat = os.stat(abs_path)
            except OSError:
                continue

            size_bytes = int(stat.st_size)
            modified_ts = float(stat.st_mtime)

            if min_size is not None and size_bytes < min_size:
                continue
            if max_size is not None and size_bytes > max_size:
                continue
            if modified_after is not None and modified_ts < modified_after:
                continue

            if requested_metadata_mode != "all":
                if supports_metadata:
                    if not metadata_summary:
                        metadata_summary = summarize_metadata(extension, abs_path)
                    metadata_obj = metadata_summary.get("metadata") if isinstance(metadata_summary.get("metadata"), dict) else {}

                    # generation (ComfyUI prompt chunk)
                    generation_obj = metadata_obj.get("generation") if isinstance(metadata_obj, dict) else {}
                    has_generation = bool(isinstance(generation_obj, dict) and generation_obj)

                    # bubba metadata chunk
                    bubba_obj = metadata_obj.get("bubba_metadata") if isinstance(metadata_obj, dict) else None
                    has_bubba_metadata = bool(bubba_obj)

                    # workflow chunk (stored as non-empty string)
                    workflow_val = metadata_obj.get("workflow") if isinstance(metadata_obj, dict) else None
                    has_workflow = bool(workflow_val and str(workflow_val).strip())
                else:
                    has_generation = False
                    has_bubba_metadata = False
                    has_workflow = False

                if requested_metadata_mode == "has_generation" and not has_generation:
                    continue
                if requested_metadata_mode == "missing_generation" and has_generation:
                    continue
                if requested_metadata_mode == "has_bubba_metadata" and not has_bubba_metadata:
                    continue
                if requested_metadata_mode == "missing_bubba_metadata" and has_bubba_metadata:
                    continue
                if requested_metadata_mode == "has_workflow" and not has_workflow:
                    continue
                if requested_metadata_mode == "missing_workflow" and has_workflow:
                    continue

            item: dict[str, Any] = {
                "name": filename,
                "path": abs_path,
                "relative_path": rel_path,
                "extension": extension,
                "size_bytes": size_bytes,
                "modified_ts": modified_ts,
            }

            if include_metadata and metadata_summary:
                item["metadata"] = metadata_summary

            if stream_fast_path:
                if matched < offset:
                    matched += 1
                    continue

                matched += 1
                files.append(item)
                if len(files) >= limit:
                    return files
                continue

            files.append(item)

    if stream_fast_path:
        return files

    def _sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        name_key = str(item.get("name") or "").lower()
        path_key = str(item.get("relative_path") or "").lower()
        if requested_sort_by == "modified":
            return (float(item.get("modified_ts") or 0.0), name_key, path_key)
        if requested_sort_by == "size":
            return (int(item.get("size_bytes") or 0), name_key, path_key)
        if requested_sort_by == "metadata":
            has_metadata = 1 if item.get("metadata") else 0
            return (has_metadata, name_key, path_key)
        return (name_key, path_key)

    files.sort(key=_sort_key, reverse=requested_sort_dir == "desc")
    return files[offset : offset + limit]
