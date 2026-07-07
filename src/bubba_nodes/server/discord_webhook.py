from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Mapping

from ..compat.paths import get_user_directory
from ..compat.routes import route_table

_route_registered = False
_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,63}$")
_STAGING_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_MAX_FILES_PER_MESSAGE = 10
_MAX_MESSAGE_LENGTH = 2000
_MAX_EMBED_FIELD_LENGTH = 1024


def _user_root() -> Path:
    return get_user_directory()


def _discord_root() -> Path:
    return _user_root() / "bubba_nodes" / "discord"


def _profiles_path() -> Path:
    return _discord_root() / "webhook_profiles.json"


def _staging_root() -> Path:
    return _discord_root() / "staged"


def _read_profiles() -> dict[str, str]:
    path = _profiles_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return {str(name): str(url) for name, url in payload.items() if isinstance(name, str) and isinstance(url, str)}


def list_profile_names() -> list[str]:
    return sorted(_read_profiles(), key=str.casefold)


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _validate_profile_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not _PROFILE_NAME_RE.fullmatch(normalized):
        raise ValueError("Profile names must be 1-64 characters using letters, numbers, spaces, dot, dash, or underscore.")
    return normalized


def _validate_webhook_url(url: str) -> str:
    normalized = str(url or "").strip()
    parsed = urllib.parse.urlparse(normalized)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or not (host == "discord.com" or host.endswith(".discord.com")):
        raise ValueError("Webhook URL must use HTTPS on discord.com.")
    if len(path_parts) < 4 or path_parts[-3] != "webhooks" or not path_parts[-2] or not path_parts[-1]:
        raise ValueError("Webhook URL does not look like a Discord webhook URL.")
    return normalized


def save_profile(name: str, url: str) -> None:
    profile_name = _validate_profile_name(name)
    webhook_url = _validate_webhook_url(url)
    profiles = _read_profiles()
    profiles[profile_name] = webhook_url
    _write_json_atomic(_profiles_path(), profiles)


def delete_profile(name: str) -> bool:
    profile_name = _validate_profile_name(name)
    profiles = _read_profiles()
    existed = profile_name in profiles
    if existed:
        profiles.pop(profile_name)
        _write_json_atomic(_profiles_path(), profiles)
    return existed


def _validate_staging_id(staging_id: Any) -> str:
    normalized = str(staging_id or "").strip()
    if not _STAGING_ID_RE.fullmatch(normalized):
        raise ValueError("Invalid Discord staging ID.")
    return normalized


def staging_directory(staging_id: Any) -> Path:
    return _staging_root() / _validate_staging_id(staging_id)


def replace_staged_payload(staging_id: Any, image_paths: list[Path], manifest: Mapping[str, Any]) -> Path:
    target = staging_directory(staging_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    temp_dir.mkdir(parents=True)
    try:
        copied_names: list[str] = []
        for index, source in enumerate(image_paths):
            suffix = source.suffix.lower() if source.suffix else ".png"
            filename = f"image_{index + 1:03d}{suffix}"
            shutil.copyfile(source, temp_dir / filename)
            copied_names.append(filename)
        stored_manifest = dict(manifest)
        stored_manifest["images"] = copied_names
        _write_json_atomic(temp_dir / "manifest.json", stored_manifest)
        if target.exists():
            shutil.rmtree(target)
        for attempt in range(5):
            try:
                temp_dir.rename(target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
        return target
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def clear_staged_payload(staging_id: Any) -> bool:
    target = staging_directory(staging_id)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _build_embed(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    if not manifest.get("include_embed", True):
        return None
    metadata = manifest.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    fields: list[dict[str, Any]] = []
    if manifest.get("include_generation_info", True):
        generation_parts = []
        if metadata.get("model_name"):
            generation_parts.append(f"Model: {metadata['model_name']}")
        if metadata.get("seed") is not None:
            generation_parts.append(f"Seed: {metadata['seed']}")
        if metadata.get("steps"):
            generation_parts.append(f"Steps: {metadata['steps']}")
        if metadata.get("cfg"):
            generation_parts.append(f"CFG: {metadata['cfg']}")
        if metadata.get("sampler_name"):
            generation_parts.append(f"Sampler: {metadata['sampler_name']}")
        if metadata.get("scheduler"):
            generation_parts.append(f"Scheduler: {metadata['scheduler']}")
        if metadata.get("denoise"):
            generation_parts.append(f"Denoise: {metadata['denoise']}")
        if generation_parts:
            fields.append({"name": "Generation", "value": _truncate("\n".join(generation_parts), _MAX_EMBED_FIELD_LENGTH)})
    if manifest.get("include_loras", True) and metadata.get("loras"):
        fields.append({"name": "LoRAs", "value": _truncate(", ".join(metadata["loras"]), _MAX_EMBED_FIELD_LENGTH)})
    if manifest.get("include_positive_prompt", True) and metadata.get("positive_prompt"):
        fields.append({"name": "Positive prompt", "value": _truncate(metadata["positive_prompt"], _MAX_EMBED_FIELD_LENGTH)})
    if manifest.get("include_negative_prompt", False) and metadata.get("negative_prompt"):
        fields.append({"name": "Negative prompt", "value": _truncate(metadata["negative_prompt"], _MAX_EMBED_FIELD_LENGTH)})
    return {"title": "Bubba Nodes generation", "fields": fields} if fields else None


def _encode_multipart(payload: Mapping[str, Any], files: list[Path]) -> tuple[bytes, str]:
    boundary = f"----BubbaNodes{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="payload_json"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            payload_json,
            b"\r\n",
        ]
    )
    for index, path in enumerate(files):
        content_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="files[{index}]"; filename="{path.name}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def _post_webhook(webhook_url: str, payload: Mapping[str, Any], files: list[Path]) -> None:
    body, boundary = _encode_multipart(payload, files)
    parsed = urllib.parse.urlparse(webhook_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "wait" for key, _value in query):
        query.append(("wait", "true"))
    request_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    request = urllib.request.Request(
        request_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Bubba-Nodes/2.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Discord returned HTTP {response.status}.")
    except urllib.error.HTTPError as error:
        detail = error.read(512).decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord returned HTTP {error.code}: {_truncate(detail, 240)}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach Discord: {error.reason}") from error


def send_staged_payload(staging_id: Any) -> dict[str, Any]:
    target = staging_directory(staging_id)
    manifest_path = target / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("No captured Discord payload is available for this node yet.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile_name = str(manifest.get("webhook_profile", "")).strip()
    profiles = _read_profiles()
    webhook_url = profiles.get(profile_name)
    if not webhook_url:
        raise ValueError(f'Discord webhook profile "{profile_name}" is not configured.')
    image_paths = [target / str(name) for name in manifest.get("images", [])]
    image_paths = [path for path in image_paths if path.is_file() and path.parent == target]
    if not image_paths:
        raise FileNotFoundError("The captured Discord payload contains no images.")
    embed = _build_embed(manifest)
    batches = [image_paths[index : index + _MAX_FILES_PER_MESSAGE] for index in range(0, len(image_paths), _MAX_FILES_PER_MESSAGE)]
    for index, batch in enumerate(batches):
        payload: dict[str, Any] = {}
        if index == 0:
            message = _truncate(manifest.get("message", ""), _MAX_MESSAGE_LENGTH)
            if message:
                payload["content"] = message
            if embed:
                payload["embeds"] = [embed]
        _post_webhook(webhook_url, payload, batch)
    return {"status": "sent", "image_count": len(image_paths), "message_count": len(batches), "profile": profile_name}


def staged_status(staging_id: Any) -> dict[str, Any]:
    target = staging_directory(staging_id)
    manifest_path = target / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "empty", "image_count": 0}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "status": "staged",
        "image_count": len(manifest.get("images", [])),
        "profile": str(manifest.get("webhook_profile", "")),
        "captured_at": str(manifest.get("captured_at", "")),
    }


def register_discord_webhook_routes() -> None:
    global _route_registered
    if _route_registered:
        return
    try:
        import asyncio
        from aiohttp import web
    except Exception:  # pragma: no cover - Comfy runtime only
        return
    routes = route_table()
    if routes is None:
        return

    @routes.get("/bubba/discord/profiles")
    async def discord_profiles_get(_request):
        return web.json_response({"profiles": list_profile_names()})

    @routes.post("/bubba/discord/profiles")
    async def discord_profiles_save(request):
        try:
            payload = await request.json()
            save_profile(payload.get("name", ""), payload.get("url", ""))
            return web.json_response({"status": "saved", "profiles": list_profile_names()})
        except ValueError as error:
            return web.json_response({"status": "error", "error": str(error)}, status=400)
        except Exception as error:
            return web.json_response({"status": "error", "error": f"Could not save profile: {error}"}, status=500)

    @routes.delete("/bubba/discord/profiles/{name}")
    async def discord_profiles_delete(request):
        try:
            deleted = delete_profile(request.match_info.get("name", ""))
            return web.json_response({"status": "deleted" if deleted else "not_found", "profiles": list_profile_names()})
        except ValueError as error:
            return web.json_response({"status": "error", "error": str(error)}, status=400)

    @routes.get("/bubba/discord/staged/{staging_id}")
    async def discord_staged_get(request):
        try:
            return web.json_response(staged_status(request.match_info.get("staging_id", "")))
        except ValueError as error:
            return web.json_response({"status": "error", "error": str(error)}, status=400)

    @routes.post("/bubba/discord/send-staged")
    async def discord_send_staged(request):
        try:
            payload = await request.json()
            result = await asyncio.to_thread(send_staged_payload, payload.get("staging_id", ""))
            return web.json_response(result)
        except (ValueError, FileNotFoundError) as error:
            return web.json_response({"status": "error", "error": str(error)}, status=400)
        except Exception as error:
            return web.json_response({"status": "error", "error": str(error)}, status=502)

    @routes.post("/bubba/discord/clear-staged")
    async def discord_clear_staged(request):
        try:
            payload = await request.json()
            cleared = clear_staged_payload(payload.get("staging_id", ""))
            return web.json_response({"status": "cleared" if cleared else "empty"})
        except ValueError as error:
            return web.json_response({"status": "error", "error": str(error)}, status=400)

    _route_registered = True
