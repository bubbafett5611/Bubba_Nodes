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
    import urllib.request
    import urllib.error
    import urllib.parse
    import json
    import mimetypes
    import os
    import re
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

    _LOCAL_TAG_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "comfyui", "danbooru_e621_merged.csv")
    _UPSTREAM_TAG_LISTS_API_URL = (
        "https://api.github.com/repos/DraconicDragon/dbr-e621-lists-archive/contents/tag-lists/danbooru_e621_merged"
    )
    _UPSTREAM_RAW_ROOT = "https://raw.githubusercontent.com/DraconicDragon/dbr-e621-lists-archive/main/tag-lists/danbooru_e621_merged"
    _TAG_EXAMPLE_ALLOWED_HOSTS = {
        "danbooru.donmai.us",
        "cdn.donmai.us",
        "hijiribe.donmai.us",
        "e621.net",
        "static1.e621.net",
    }

    _FILENAME_DATE_RE = re.compile(r"danbooru_e621_merged_(\d{4}-\d{2}-\d{2})_.*\.csv$", re.IGNORECASE)

    # Server-side embeddings cache: persists for the lifetime of the server process
    _embeddings_cache = {"items": None}

    def _pick_latest_upstream_csv(entries: list[dict]) -> str:
        candidates: list[tuple[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("type", "")) != "file":
                continue
            name = str(entry.get("name", ""))
            match = _FILENAME_DATE_RE.match(name)
            if not match:
                continue
            date_key = match.group(1)
            candidates.append((date_key, name))

        if not candidates:
            raise RuntimeError("No merged CSV files found in upstream folder.")

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _download_text(url: str, headers: dict[str, str] | None = None) -> str:
        merged_headers = {"User-Agent": "bubba_nodes/0.0.1"}
        if isinstance(headers, dict):
            merged_headers.update(headers)
        req = urllib.request.Request(url, headers=merged_headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return data.decode("utf-8", errors="replace")

    def _to_absolute_url(base: str, url: str | None) -> str:
        raw = str(url or "").strip()
        if not raw:
            return ""
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if raw.startswith("//"):
            return f"https:{raw}"
        return urllib.parse.urljoin(base, raw)

    def _is_allowed_tag_example_image_url(raw_url: str) -> bool:
        try:
            parsed = urllib.parse.urlsplit(str(raw_url or "").strip())
        except Exception:
            return False

        if parsed.scheme not in {"http", "https"}:
            return False

        host = (parsed.hostname or "").lower().strip(".")
        if not host:
            return False

        if host in _TAG_EXAMPLE_ALLOWED_HOSTS:
            return True

        return host.endswith(".donmai.us") or host.endswith(".e621.net")

    def _is_danbooru_excluded_post(post: dict[str, object]) -> bool:
        ext = str(post.get("file_ext", "") or "").lower()
        return ext in {"webm", "mp4", "swf", "gif"}

    def _is_e621_excluded_post(post: dict[str, object]) -> bool:
        file_obj = post.get("file") if isinstance(post.get("file"), dict) else {}
        ext = str(file_obj.get("ext", "") or "").lower()
        return ext in {"webm", "mp4", "swf", "gif"}

    def _fetch_danbooru_example(tag: str) -> dict[str, object]:
        # Use the known-good Danbooru query pattern for fast, image-only results.
        candidate_queries = [
            f"{tag} order:score age:<1month -is:mp4 -is:gif",
        ]

        last_error = ""
        post: dict[str, object] = {}

        for tag_query in candidate_queries:
            query = urllib.parse.urlencode({"tags": tag_query, "limit": "1"})
            url = f"https://danbooru.donmai.us/posts.json?{query}"
            try:
                payload = json.loads(_download_text(url))
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                # Retry with next fallback on unprocessable/invalid query combinations.
                if exc.code == 422:
                    continue
                raise

            posts = payload if isinstance(payload, list) else []
            normalized_posts = [entry for entry in posts if isinstance(entry, dict)]
            image_posts = [entry for entry in normalized_posts if not _is_danbooru_excluded_post(entry)]
            if image_posts:
                post = image_posts[0]
                break

        if not post:
            result: dict[str, object] = {"site": "danbooru", "status": "empty"}
            if last_error:
                result["error"] = last_error
            return result

        post_id = post.get("id")
        post_url = f"https://danbooru.donmai.us/posts/{post_id}" if post_id is not None else ""
        image_url = _to_absolute_url(
            "https://danbooru.donmai.us",
            post.get("large_file_url") or post.get("file_url") or post.get("preview_file_url"),
        )
        return {
            "site": "danbooru",
            "status": "ok" if image_url else "empty",
            "post_url": post_url,
            "image_url": image_url,
            "post_id": post_id,
            "score": post.get("score") or 0,
        }

    def _fetch_e621_example(tag: str) -> dict[str, object]:
        # Some top-scoring posts may be unavailable for preview/file URL even though the tag has results.
        # Pull a small window and pick the first post that has a usable image URL.
        query = urllib.parse.urlencode({"tags": f"{tag} order:score -type:webm -type:swf -type:mp4 -type:gif", "limit": "10"})
        url = f"https://e621.net/posts.json?{query}"
        payload = json.loads(
            _download_text(
                url,
                headers={
                    "User-Agent": "bubba_nodes/0.0.1 (contact: metalgfx@gmail.com)",
                    "Accept": "application/json",
                },
            )
        )
        posts = payload.get("posts") if isinstance(payload, dict) else []
        posts = posts if isinstance(posts, list) else []
        if not posts:
            return {"site": "e621", "status": "empty"}

        post = {}
        image_url = ""
        for entry in posts:
            if not isinstance(entry, dict):
                continue
            if _is_e621_excluded_post(entry):
                continue

            sample = entry.get("sample") if isinstance(entry.get("sample"), dict) else {}
            file_obj = entry.get("file") if isinstance(entry.get("file"), dict) else {}
            preview = entry.get("preview") if isinstance(entry.get("preview"), dict) else {}
            candidate_url = _to_absolute_url(
                "https://e621.net",
                sample.get("url") or file_obj.get("url") or preview.get("url"),
            )
            if not candidate_url:
                continue

            post = entry
            image_url = candidate_url
            break

        if not post:
            return {
                "site": "e621",
                "status": "empty",
                "error": "No usable image URL found in top results.",
            }

        post_id = post.get("id")
        post_url = f"https://e621.net/posts/{post_id}" if post_id is not None else ""
        score_obj = post.get("score") if isinstance(post.get("score"), dict) else {}
        score = score_obj.get("total") if isinstance(score_obj, dict) else 0
        return {
            "site": "e621",
            "status": "ok" if image_url else "empty",
            "post_url": post_url,
            "image_url": image_url,
            "post_id": post_id,
            "score": score or 0,
        }

    @PromptServer.instance.routes.post("/bubba/sync_upstream_cache")
    async def _sync_upstream_cache(request):
        del request
        try:
            listing_text = _download_text(_UPSTREAM_TAG_LISTS_API_URL)
            listing_payload = json.loads(listing_text)
            if not isinstance(listing_payload, list):
                raise RuntimeError("Unexpected upstream listing payload.")

            latest_name = _pick_latest_upstream_csv(listing_payload)
            source_url = f"{_UPSTREAM_RAW_ROOT}/{latest_name}"
            csv_text = _download_text(source_url)

            if not csv_text or csv_text.count("\n") < 1000:
                raise RuntimeError("Downloaded CSV looks too small or empty.")

            os.makedirs(os.path.dirname(_LOCAL_TAG_CACHE_PATH), exist_ok=True)
            header = "name,category,count,aliases\n"
            if not csv_text.startswith("name,") and not csv_text.startswith("tag,"):
                csv_text = header + csv_text
            with open(_LOCAL_TAG_CACHE_PATH, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(csv_text)

            return web.json_response(
                {
                    "status": "ok",
                    "filename": latest_name,
                    "source_url": source_url,
                    "written_path": _LOCAL_TAG_CACHE_PATH,
                    "line_count": csv_text.count("\n"),
                }
            )
        except urllib.error.URLError as exc:
            return web.json_response({"error": f"Upstream request failed: {exc}"}, status=502)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    def _to_embedding_autocomplete_entry(raw_name: str) -> dict[str, object] | None:
        name = str(raw_name or "").strip()
        if not name:
            return None

        normalized = name.replace("\\", "/").strip("/")
        if not normalized:
            return None

        stem, _ext = os.path.splitext(normalized)
        if stem:
            normalized = stem

        backslash_name = normalized.replace("/", "\\")
        leaf = backslash_name.split("\\")[-1] if backslash_name else ""

        aliases = [
            f"embedding:{normalized}",
            f"embedding:{backslash_name}",
            normalized,
            backslash_name,
        ]
        if leaf:
            aliases.extend([leaf, f"embedding:{leaf}"])

        deduped_aliases: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            key = alias.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_aliases.append(alias)

        return {
            "text": f"embedding:{backslash_name}",
            "aliases": deduped_aliases,
        }

    def _get_embeddings_cached() -> tuple[list[dict[str, object]], str]:
        """Get embeddings list from cache or build it once. Returns (items, status)."""
        import folder_paths  # type: ignore

        # Return cached items if available (cache persists for server lifetime)
        if _embeddings_cache["items"] is not None:
            return _embeddings_cache["items"], "cached"

        # Build cache from filesystem (first access only)
        try:
            if not hasattr(folder_paths, "get_filename_list"):
                return [], "folder_paths_unavailable"

            raw_embeddings = folder_paths.get_filename_list("embeddings")
            items: list[dict[str, object]] = []
            for raw in raw_embeddings or []:
                entry = _to_embedding_autocomplete_entry(str(raw))
                if entry is not None:
                    items.append(entry)

            # Cache for the lifetime of the server
            _embeddings_cache["items"] = items

            return items, "ok"
        except Exception as exc:
            return [], f"error: {exc}"

    @PromptServer.instance.routes.get("/bubba/autocomplete/embeddings")
    async def _autocomplete_embeddings(request):
        del request
        try:
            import folder_paths  # type: ignore
        except Exception:
            folder_paths = None

        if folder_paths is None or not hasattr(folder_paths, "get_filename_list"):
            return web.json_response({"embeddings": [], "count": 0, "status": "folder_paths_unavailable"})

        items, status = _get_embeddings_cached()
        return web.json_response({"embeddings": items, "count": len(items), "status": status})

    @PromptServer.instance.routes.get("/bubba/tag_examples")
    async def _tag_examples(request):
        raw_tag = str(request.query.get("tag", "") or "").strip()
        tag = raw_tag[:120]
        if not tag:
            return web.json_response({"error": "Missing tag parameter."}, status=400)

        def _capture(fetch_fn):
            try:
                return fetch_fn(tag)
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        danbooru = _capture(_fetch_danbooru_example)
        e621 = _capture(_fetch_e621_example)

        return web.json_response(
            {
                "tag": tag,
                "examples": {
                    "danbooru": danbooru,
                    "e621": e621,
                },
            },
            dumps=lambda payload: json.dumps(payload, ensure_ascii=False),
        )

    @PromptServer.instance.routes.get("/bubba/tag_example_image")
    async def _tag_example_image(request):
        raw_url = str(request.query.get("url", "") or "").strip()
        if not raw_url:
            return web.json_response({"error": "Missing image URL."}, status=400)

        if not _is_allowed_tag_example_image_url(raw_url):
            return web.json_response({"error": "Image host is not allowed."}, status=403)

        parsed = urllib.parse.urlsplit(raw_url)
        host = (parsed.hostname or "").lower()
        headers = {
            "User-Agent": "bubba_nodes/0.0.1",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }

        # Danbooru media servers may enforce hotlinking rules unless a referer is set.
        if host.endswith(".donmai.us") or host == "danbooru.donmai.us":
            headers["Referer"] = "https://danbooru.donmai.us/"

        try:
            req = urllib.request.Request(raw_url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
                content_type = str(resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        except urllib.error.HTTPError as exc:
            return web.json_response({"error": f"Upstream image request failed: HTTP {exc.code}"}, status=502)
        except urllib.error.URLError as exc:
            return web.json_response({"error": f"Upstream image request failed: {exc}"}, status=502)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

        if not content_type or not content_type.startswith("image/"):
            guessed, _enc = mimetypes.guess_type(raw_url)
            content_type = guessed or "application/octet-stream"

        return web.Response(
            body=data,
            content_type=content_type,
            headers={"Cache-Control": "public, max-age=600"},
        )

    def _build_cache_headers(path: str, variant: str = "", max_age: int = 0) -> tuple[dict[str, str], float]:
        stat = os.stat(path)
        mtime = float(stat.st_mtime)
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(mtime * 1_000_000_000)))
        tag = f'W/"{mtime_ns:x}-{int(stat.st_size):x}-{variant}"'
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
        sort_by = str(query.get("sort_by", "name") or "name").strip().lower()
        sort_dir = str(query.get("sort_dir", "asc") or "asc").strip().lower()
        metadata_mode = str(query.get("metadata_mode", "all") or "all").strip().lower()

        try:
            min_size_bytes = int(query.get("min_size_bytes", "")) if query.get("min_size_bytes") else None
        except ValueError:
            min_size_bytes = None

        try:
            max_size_bytes = int(query.get("max_size_bytes", "")) if query.get("max_size_bytes") else None
        except ValueError:
            max_size_bytes = None

        try:
            modified_after_ts = float(query.get("modified_after_ts", "")) if query.get("modified_after_ts") else None
        except ValueError:
            modified_after_ts = None

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
            sort_by=sort_by,
            sort_dir=sort_dir,
            min_size_bytes=min_size_bytes,
            max_size_bytes=max_size_bytes,
            modified_after_ts=modified_after_ts,
            metadata_mode=metadata_mode,
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

        # requested_root = ""
        requested_paths = []
        if isinstance(payload, dict):
            # requested_root = str(payload.get("root", "") or "")
            # Support both single file (legacy) and bulk delete (new)
            if "path" in payload:
                requested_paths = [str(payload.get("path", "") or "")]
            elif "paths" in payload and isinstance(payload.get("paths"), list):
                requested_paths = [str(p or "") for p in payload.get("paths", [])]

        if not requested_paths:
            return web.json_response({"error": "No paths provided"}, status=400)

        # # Resolve root
        # try:
        #     root_path = resolve_requested_root(requested_root, roots) if requested_root else roots[0].path
        # except ValueError as exc:
        #     return web.json_response({"error": str(exc)}, status=400)

        deleted_paths = []
        errors = []

        for file_path_str in requested_paths:
            try:
                file_path = resolve_requested_file(file_path_str, roots)
            except ValueError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})
                continue
            except FileNotFoundError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})
                continue
            except PermissionError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})
                continue

            try:
                os.remove(file_path)
                deleted_paths.append(file_path)
            except FileNotFoundError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})
            except PermissionError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})
            except OSError as exc:
                errors.append({"path": file_path_str, "error": str(exc)})

        return web.json_response(
            {
                "status": "ok",
                "deleted_count": len(deleted_paths),
                "deleted_paths": deleted_paths,
                "errors": errors,
            }
        )

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
