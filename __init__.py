"""Top-level package for bubba_nodes."""

# TODO(optimize): Defer node imports until first access to reduce startup cost when Comfy scans many custom node packages.
# TODO(new-feature): Emit a clear warning message in placeholder mode so missing runtime dependencies are easier to diagnose.

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]

__author__ = """BubbaNodes"""
__email__ = "metalgfx@gmail.com"
__version__ = "0.0.1"

# Import with graceful handling for test environments where ComfyUI's nodes module may not be available
try:
    from .src.bubba_nodes.nodes import NODE_CLASS_MAPPINGS
    from .src.bubba_nodes.nodes import NODE_DISPLAY_NAME_MAPPINGS
except ImportError as e:
    # During testing, the ComfyUI nodes module may not be available, so create placeholders
    if "nodes" in str(e):
        NODE_CLASS_MAPPINGS = {}
        NODE_DISPLAY_NAME_MAPPINGS = {}
    else:
        raise

WEB_DIRECTORY = "./web"

try:
    from email.utils import formatdate, parsedate_to_datetime
    import json
    import mimetypes
    import os
    import platform
    import subprocess
    from aiohttp import web
    from server import PromptServer
    from .src.bubba_nodes.utils.asset_viewer import (
        ALLOWED_UPLOAD_IMAGE_EXTENSIONS,
        build_asset_item,
        discover_asset_roots,
        find_root_for_path,
        generate_thumbnail_bytes,
        make_unique_destination_path,
        resolve_requested_file,
        resolve_requested_root,
        sanitize_upload_filename,
        scan_assets,
    )

    _CACHE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "web", "comfyui", "danbooru_cache.csv"
    )

    def _build_cache_headers(path: str, variant: str = "", max_age: int = 0) -> tuple[dict[str, str], float]:
        stat = os.stat(path)
        mtime = float(stat.st_mtime)
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(mtime * 1_000_000_000)))
        tag = f"W/\"{mtime_ns:x}-{int(stat.st_size):x}-{variant}\""
        headers = {
            "ETag": tag,
            "Last-Modified": formatdate(mtime, usegmt=True),
            "Cache-Control": f"private, max-age={max(0, int(max_age))}, must-revalidate",
        }
        return headers, mtime

    def _is_not_modified(request, etag: str, mtime: float) -> bool:
        incoming_etag = request.headers.get("If-None-Match", "")
        if incoming_etag:
            tags = [part.strip() for part in incoming_etag.split(",") if part.strip()]
            if "*" in tags or etag in tags:
                return True

        incoming_modified_since = request.headers.get("If-Modified-Since", "")
        if incoming_modified_since:
            try:
                since_dt = parsedate_to_datetime(incoming_modified_since)
                if since_dt.timestamp() >= int(mtime):
                    return True
            except Exception:
                pass

        return False

    @PromptServer.instance.routes.get("/bubba/open_cache")
    async def _open_cache(request):
        print(f"[bubba_nodes] opening cache file: {_CACHE_PATH}")
        if platform.system() == "Windows":
            os.startfile(_CACHE_PATH)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", _CACHE_PATH])
        else:
            subprocess.Popen(["xdg-open", _CACHE_PATH])
        return web.json_response({"status": "ok"})

    @PromptServer.instance.routes.post("/bubba/write_cache")
    async def _write_cache(request):
        csv_text = await request.text()
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(csv_text)
        print(f"[bubba_nodes] wrote cache file: {_CACHE_PATH} ({len(csv_text)} bytes)")
        return web.json_response({"status": "ok"})

    @PromptServer.instance.routes.get("/bubba/assets/roots")
    async def _asset_roots(request):
        roots = discover_asset_roots()
        payload = [{"key": root.key, "label": root.label, "path": root.path} for root in roots]
        return web.json_response({"roots": payload})

    @PromptServer.instance.routes.get("/bubba/assets/list")
    async def _asset_list(request):
        roots = discover_asset_roots()
        query = request.query

        requested_root = query.get("root")
        search_query = query.get("q", "")
        extensions_raw = query.get("ext", "")
        include_metadata = query.get("include_metadata", "false").lower() != "false"

        try:
            limit = int(query.get("limit", "600"))
        except ValueError:
            limit = 600

        try:
            offset = int(query.get("offset", "0"))
        except ValueError:
            offset = 0

        extensions = [item.strip() for item in extensions_raw.split(",") if item.strip()]

        try:
            selected_root = resolve_requested_root(requested_root, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        assets = scan_assets(
            root=selected_root,
            query=search_query,
            extensions=extensions,
            limit=limit + 1,
            include_metadata=include_metadata,
            offset=offset,
            search_in_metadata=True,
        )

        has_more = len(assets) > limit
        if has_more:
            assets = assets[:limit]
        next_offset = offset + len(assets) if has_more else None
        selected_root_key = next((root.key for root in roots if os.path.abspath(root.path) == os.path.abspath(selected_root)), "")

        return web.json_response(
            {
                "root": selected_root,
                "root_key": selected_root_key,
                "count": len(assets),
                "assets": assets,
                "offset": offset,
                "next_offset": next_offset,
                "has_more": has_more,
            },
            dumps=lambda payload: json.dumps(payload, ensure_ascii=False),
        )

    @PromptServer.instance.routes.get("/bubba/assets/details")
    async def _asset_details(request):
        roots = discover_asset_roots()
        requested_path = request.query.get("path", "")

        try:
            file_path = resolve_requested_file(requested_path, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)

        root = find_root_for_path(file_path, roots)
        if root is None:
            return web.json_response({"error": "Unable to resolve file root."}, status=400)

        try:
            asset = build_asset_item(file_path, root.path, include_metadata=True)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except FileNotFoundError:
            return web.json_response({"error": "File does not exist."}, status=404)
        except OSError as exc:
            return web.json_response({"error": str(exc)}, status=500)

        return web.json_response({"asset": asset}, dumps=lambda payload: json.dumps(payload, ensure_ascii=False))

    @PromptServer.instance.routes.get("/bubba/assets/thumb")
    async def _asset_thumb(request):
        roots = discover_asset_roots()
        requested_path = request.query.get("path", "")

        try:
            file_path = resolve_requested_file(requested_path, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)

        try:
            size = int(request.query.get("size", "256"))
        except ValueError:
            size = 256

        cache_headers, mtime = _build_cache_headers(file_path, variant=f"thumb-{size}", max_age=300)
        if _is_not_modified(request, cache_headers["ETag"], mtime):
            return web.Response(status=304, headers=cache_headers)

        thumb = generate_thumbnail_bytes(file_path, max_size=size)
        if thumb is None:
            response = web.FileResponse(path=file_path)
            response.headers.update(cache_headers)
            response.content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            return response

        return web.Response(body=thumb, content_type="image/png", headers=cache_headers)

    @PromptServer.instance.routes.get("/bubba/assets/file")
    async def _asset_file(request):
        roots = discover_asset_roots()
        requested_path = request.query.get("path", "")

        try:
            file_path = resolve_requested_file(requested_path, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)

        cache_headers, mtime = _build_cache_headers(file_path, variant="file", max_age=60)
        if _is_not_modified(request, cache_headers["ETag"], mtime):
            return web.Response(status=304, headers=cache_headers)

        response = web.FileResponse(path=file_path)
        response.headers.update(cache_headers)
        return response

    @PromptServer.instance.routes.post("/bubba/assets/delete")
    async def _asset_delete(request):
        roots = discover_asset_roots()

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        requested_path = ""
        if isinstance(payload, dict):
            requested_path = str(payload.get("path", "") or "")

        try:
            file_path = resolve_requested_file(requested_path, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)

        try:
            os.remove(file_path)
        except FileNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except PermissionError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except OSError as exc:
            return web.json_response({"error": str(exc)}, status=500)

        return web.json_response({"status": "ok", "deleted_path": file_path})

    @PromptServer.instance.routes.post("/bubba/assets/upload")
    async def _asset_upload(request):
        roots = discover_asset_roots()
        requested_root = request.query.get("root", "")

        try:
            selected_root = resolve_requested_root(requested_root, roots)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        if not os.path.isdir(selected_root):
            return web.json_response({"error": "Selected root directory does not exist."}, status=400)

        try:
            reader = await request.multipart()
        except Exception:
            return web.json_response({"error": "Expected multipart form data."}, status=400)

        uploaded: list[dict[str, object]] = []
        skipped: list[dict[str, str]] = []

        part = await reader.next()
        while part is not None:
            filename = str(getattr(part, "filename", "") or "")
            if filename:
                safe_name = sanitize_upload_filename(filename)
                extension = os.path.splitext(safe_name)[1].lower()
                if extension not in ALLOWED_UPLOAD_IMAGE_EXTENSIONS:
                    skipped.append({"name": filename, "reason": "Unsupported file type."})
                    while await part.read_chunk():
                        pass
                    part = await reader.next()
                    continue

                destination = make_unique_destination_path(selected_root, safe_name)
                bytes_written = 0
                try:
                    with open(destination, "wb") as handle:
                        while True:
                            chunk = await part.read_chunk()
                            if not chunk:
                                break
                            handle.write(chunk)
                            bytes_written += len(chunk)
                except PermissionError as exc:
                    return web.json_response({"error": str(exc)}, status=403)
                except OSError as exc:
                    return web.json_response({"error": str(exc)}, status=500)

                if bytes_written <= 0:
                    try:
                        os.remove(destination)
                    except OSError:
                        pass
                    skipped.append({"name": filename, "reason": "File was empty."})
                else:
                    try:
                        uploaded.append(build_asset_item(destination, selected_root, include_metadata=False))
                    except Exception:
                        uploaded.append(
                            {
                                "name": os.path.basename(destination),
                                "path": destination,
                                "relative_path": os.path.relpath(destination, selected_root),
                            }
                        )
            part = await reader.next()

        if not uploaded and skipped:
            return web.json_response({"error": "No files were uploaded.", "skipped": skipped}, status=400)

        selected_root_key = next(
            (root.key for root in roots if os.path.abspath(root.path) == os.path.abspath(selected_root)),
            "",
        )
        return web.json_response(
            {
                "status": "ok",
                "root": selected_root,
                "root_key": selected_root_key,
                "uploaded": uploaded,
                "skipped": skipped,
            },
            dumps=lambda payload: json.dumps(payload, ensure_ascii=False),
        )

except ImportError as exc:
    print(f"[bubba_nodes] Web route setup skipped due to missing dependency: {exc}")
except Exception as exc:
    print(f"[bubba_nodes] Web route setup failed: {exc}")
