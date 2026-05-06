from __future__ import annotations

import json
import re
from pathlib import Path

_PREVIEW_EXTENSIONS = ("jpeg", "jpg", "png", "webp")
_route_registered = False
_CIVITAI_URL_RE = re.compile(r"https?://(?:www\.)?civitai\.(?:com|red)/models/\d+(?:[^\s\"'>]*)", re.IGNORECASE)


def _build_preview_candidates(checkpoint_file: Path) -> list[Path]:
    stem = checkpoint_file.with_suffix("")
    candidates: list[Path] = []
    for ext in _PREVIEW_EXTENSIONS:
        candidates.append(Path(f"{stem}.preview.{ext}"))
    for ext in _PREVIEW_EXTENSIONS:
        candidates.append(Path(f"{stem}.{ext}"))
    return candidates


def _resolve_checkpoint_path(model: str, folder_paths_module) -> Path | None:
    if folder_paths_module is None:
        return None

    normalized = str(model or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    if ".." in normalized.split("/"):
        return None

    if hasattr(folder_paths_module, "get_full_path"):
        resolved = folder_paths_module.get_full_path("checkpoints", normalized)
        if resolved:
            path = Path(resolved)
            if path.exists():
                return path

    if hasattr(folder_paths_module, "get_folder_paths"):
        for base in folder_paths_module.get_folder_paths("checkpoints"):
            base_path = Path(base).resolve()
            candidate = (base_path / normalized).resolve()
            if not str(candidate).startswith(str(base_path)):
                continue
            if candidate.exists():
                return candidate

    return None


def _resolve_lora_path(model: str, folder_paths_module) -> Path | None:
    if folder_paths_module is None:
        return None

    normalized = str(model or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    if ".." in normalized.split("/"):
        return None

    if hasattr(folder_paths_module, "get_full_path"):
        resolved = folder_paths_module.get_full_path("loras", normalized)
        if resolved:
            path = Path(resolved)
            if path.exists():
                return path

    if hasattr(folder_paths_module, "get_folder_paths"):
        for base in folder_paths_module.get_folder_paths("loras"):
            base_path = Path(base).resolve()
            candidate = (base_path / normalized).resolve()
            if not str(candidate).startswith(str(base_path)):
                continue
            if candidate.exists():
                return candidate

    return None


def _normalize_civitai_url(url: str) -> str:
    candidate = str(url or "").strip()
    if not candidate:
        return ""
    candidate = candidate.replace("civitai.com", "civitai.red")
    return candidate


def _extract_url_from_json_value(value) -> str | None:
    if isinstance(value, str):
        match = _CIVITAI_URL_RE.search(value)
        if match:
            return _normalize_civitai_url(match.group(0))
        return None

    if isinstance(value, dict):
        direct_keys = (
            "url",
            "modelUrl",
            "model_url",
            "civitaiUrl",
            "civitai_url",
            "website",
            "modelPage",
            "model_page",
        )
        for key in direct_keys:
            maybe = value.get(key)
            if isinstance(maybe, str):
                parsed = _extract_url_from_json_value(maybe)
                if parsed:
                    return parsed

        for nested in value.values():
            parsed = _extract_url_from_json_value(nested)
            if parsed:
                return parsed
        return None

    if isinstance(value, list):
        for nested in value:
            parsed = _extract_url_from_json_value(nested)
            if parsed:
                return parsed
        return None

    return None


def _collect_ids_from_json(value) -> tuple[int | None, int | None]:
    model_id: int | None = None
    version_id: int | None = None

    def _walk(node):
        nonlocal model_id, version_id
        if isinstance(node, dict):
            for key, val in node.items():
                k = str(key).strip().lower().replace("_", "")
                if isinstance(val, (int, float)):
                    num = int(val)
                    if k in ("modelid", "civitaiid", "basemodelid") and model_id is None:
                        model_id = num
                    if k in ("modelversionid", "versionid", "civitaiversionid") and version_id is None:
                        version_id = num
                _walk(val)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(value)
    return model_id, version_id


def _build_civitai_url_from_ids(model_id: int | None, version_id: int | None) -> str | None:
    if model_id is None:
        return None
    if version_id is None:
        return f"https://civitai.red/models/{model_id}"
    return f"https://civitai.red/models/{model_id}?modelVersionId={version_id}"


def _resolve_civitai_url(checkpoint_file: Path) -> str | None:
    stem = checkpoint_file.with_suffix("")
    sidecars = (
        Path(f"{stem}.civitai.info"),
        Path(f"{stem}.cm-info.json"),
        Path(f"{stem}.metadata.json"),
    )

    best_model_id: int | None = None
    best_version_id: int | None = None

    for sidecar in sidecars:
        if not sidecar.exists() or not sidecar.is_file():
            continue
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            continue

        direct = _extract_url_from_json_value(payload)
        if direct:
            return direct

        model_id, version_id = _collect_ids_from_json(payload)
        if best_model_id is None and model_id is not None:
            best_model_id = model_id
        if best_version_id is None and version_id is not None:
            best_version_id = version_id

    return _build_civitai_url_from_ids(best_model_id, best_version_id)


def register_checkpoint_preview_route() -> None:
    global _route_registered
    if _route_registered:
        return

    try:
        from aiohttp import web
        from server import PromptServer
        import folder_paths
    except Exception:  # pragma: no cover - only used in Comfy runtime
        return

    if PromptServer is None or not getattr(PromptServer, "instance", None):
        return

    routes = PromptServer.instance.routes

    @routes.get("/bubba/checkpoint_preview")
    async def bubba_checkpoint_preview(request):
        model = request.rel_url.query.get("model", "")
        checkpoint_path = _resolve_checkpoint_path(model, folder_paths)
        if checkpoint_path is None:
            return web.Response(status=404, text="checkpoint not found")

        for candidate in _build_preview_candidates(checkpoint_path):
            if candidate.exists() and candidate.is_file():
                return web.FileResponse(path=candidate)

        return web.Response(status=404, text="preview not found")

    @routes.get("/bubba/checkpoint_civitai_link")
    async def bubba_checkpoint_civitai_link(request):
        model = request.rel_url.query.get("model", "")
        checkpoint_path = _resolve_checkpoint_path(model, folder_paths)
        if checkpoint_path is None:
            return web.json_response({"url": None, "error": "checkpoint not found"}, status=404)

        url = _resolve_civitai_url(checkpoint_path)
        if not url:
            return web.json_response({"url": None})

        return web.json_response({"url": url})

    @routes.get("/bubba/lora_preview")
    async def bubba_lora_preview(request):
        model = request.rel_url.query.get("model", "")
        lora_path = _resolve_lora_path(model, folder_paths)
        if lora_path is None:
            return web.Response(status=404, text="lora not found")

        for candidate in _build_preview_candidates(lora_path):
            if candidate.exists() and candidate.is_file():
                return web.FileResponse(path=candidate)

        return web.Response(status=404, text="preview not found")

    @routes.get("/bubba/lora_civitai_link")
    async def bubba_lora_civitai_link(request):
        model = request.rel_url.query.get("model", "")
        lora_path = _resolve_lora_path(model, folder_paths)
        if lora_path is None:
            return web.json_response({"url": None, "error": "lora not found"}, status=404)

        url = _resolve_civitai_url(lora_path)
        if not url:
            return web.json_response({"url": None})

        return web.json_response({"url": url})

    _route_registered = True
