from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..compat.paths import get_filename_list
from ..compat.routes import route_table

_route_registered = False
_ARCHIVE_RAW_BASE_URL = "https://raw.githubusercontent.com/DraconicDragon/dbr-e621-lists-archive/main/tag-lists"
_DEFAULT_DANBOORU_CSV_URL = f"{_ARCHIVE_RAW_BASE_URL}/danbooru/danbooru_2026-04-01_pt20-ia-dd.csv"
_DEFAULT_E621_CSV_URL = f"{_ARCHIVE_RAW_BASE_URL}/e621/e621_2026-04-01_pt20-ia-ed.csv"
_DEFAULT_LEGACY_MERGED_CSV_URL = (
    "https://raw.githubusercontent.com/DraconicDragon1/danbooru-e621-autocomplete/main/danbooru_e621_merged.csv"
)
_MAX_CSV_DOWNLOAD_BYTES = 100 * 1024 * 1024
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class TagSource:
    name: str
    filename: str
    env_var: str
    default_url: str


def _repo_root() -> Path:
    # src/bubba_nodes/server/autocomplete.py -> repo root at parents[3]
    return Path(__file__).resolve().parents[3]


def _local_csv_path() -> Path:
    return _repo_root() / "web" / "comfyui" / "danbooru_e621_merged.csv"


def _upstream_csv_url() -> str:
    return os.getenv("BUBBA_UPSTREAM_CSV_URL", _DEFAULT_LEGACY_MERGED_CSV_URL)


def _local_tags_dir() -> Path:
    return _repo_root() / "web" / "comfyui" / "tags"


def _wildcards_dir() -> Path:
    return _repo_root() / "src" / "bubba_nodes" / "data" / "wildcards"


def _wildcard_entries(wildcards_dir: Path | None = None) -> list[dict[str, str]]:
    root = (wildcards_dir or _wildcards_dir()).resolve()
    if not root.is_dir():
        return []

    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.txt"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(root).with_suffix("").as_posix()
        except ValueError:
            continue
        if not relative:
            continue
        entries.append(
            {
                "text": relative,
                "insert_text": f"__{relative}__",
            }
        )
    return entries


def _tag_sources() -> list[TagSource]:
    return [
        TagSource("danbooru", "danbooru.csv", "BUBBA_DANBOORU_CSV_URL", _DEFAULT_DANBOORU_CSV_URL),
        TagSource("e621", "e621.csv", "BUBBA_E621_CSV_URL", _DEFAULT_E621_CSV_URL),
    ]


def _tag_source_url(source: TagSource) -> str:
    return os.getenv(source.env_var, source.default_url)


def _download_upstream_csv(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "bubba-nodes/1.0"},
    )
    chunks: list[bytes] = []
    total_bytes = 0
    with urllib.request.urlopen(request, timeout=30) as response:
        while True:
            chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_CSV_DOWNLOAD_BYTES:
                raise ValueError(f"Downloaded CSV exceeds {_MAX_CSV_DOWNLOAD_BYTES // (1024 * 1024)} MB limit.")
            chunks.append(chunk)
    payload = b"".join(chunks)
    if not payload:
        raise ValueError("Downloaded CSV is empty.")
    if b"\n" not in payload[:4096]:
        raise ValueError("Downloaded CSV does not look like a tag CSV file.")
    return payload


def _save_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_name = handle.name
            handle.write(data)
        Path(temp_name).replace(path)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


def _embedding_entry(raw_name: str) -> dict[str, object]:
    name = str(raw_name or "").strip()
    if not name:
        return {"text": "", "aliases": []}

    stem = Path(name).stem
    text = stem or name
    aliases: list[str] = []
    if stem and stem != name:
        aliases.append(name)

    return {
        "text": text,
        "aliases": aliases,
    }


def register_autocomplete_routes() -> None:
    global _route_registered
    if _route_registered:
        return

    try:
        from aiohttp import web
    except Exception:  # pragma: no cover - only used in Comfy runtime
        return

    routes = route_table()
    if routes is None:
        return

    @routes.get("/bubba/autocomplete/embeddings")
    async def bubba_autocomplete_embeddings(_request):
        try:
            names = get_filename_list("embeddings")
        except Exception:
            names = []

        entries = [_embedding_entry(name) for name in names]
        entries = [entry for entry in entries if entry.get("text")]

        return web.json_response(
            {
                "status": "ok",
                "embeddings": entries,
                "count": len(entries),
            }
        )

    @routes.get("/bubba/autocomplete/wildcards")
    async def bubba_autocomplete_wildcards(_request):
        entries = _wildcard_entries()
        return web.json_response(
            {
                "status": "ok",
                "wildcards": entries,
                "count": len(entries),
            }
        )

    @routes.post("/bubba/sync_upstream_cache")
    async def bubba_sync_upstream_cache(_request):
        results = []

        for source in _tag_sources():
            target = _local_tags_dir() / source.filename
            url = _tag_source_url(source)

            try:
                payload = _download_upstream_csv(url)
                _save_bytes_atomic(target, payload)
            except urllib.error.HTTPError as error:
                return web.json_response(
                    {
                        "status": "error",
                        "source": source.name,
                        "error": f"{source.name} upstream responded with HTTP {error.code}.",
                    },
                    status=502,
                )
            except urllib.error.URLError as error:
                return web.json_response(
                    {
                        "status": "error",
                        "source": source.name,
                        "error": f"Unable to reach {source.name} upstream source: {error.reason}",
                    },
                    status=502,
                )
            except Exception as error:
                return web.json_response(
                    {
                        "status": "error",
                        "source": source.name,
                        "error": f"Failed to sync {source.name} CSV: {error}",
                    },
                    status=500,
                )

            results.append(
                {
                    "source": source.name,
                    "source_url": url,
                    "target": str(target),
                    "bytes": len(payload),
                }
            )

        return web.json_response(
            {
                "status": "ok",
                "sources": results,
                "bytes": sum(result["bytes"] for result in results),
            }
        )

    _route_registered = True
