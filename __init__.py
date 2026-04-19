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
    import os
    import platform
    import subprocess
    from aiohttp import web
    from server import PromptServer

    _CACHE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "web", "comfyui", "danbooru_cache.csv"
    )

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

except Exception:
    pass
