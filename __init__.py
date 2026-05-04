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
__version__ = "1.0.0"

try:
    from .src.bubba_nodes.server import (
        register_checkpoint_preview_route,
        register_autocomplete_routes,
    )
except Exception:
    register_checkpoint_preview_route = None
    register_autocomplete_routes = None

if register_checkpoint_preview_route is not None:
    try:
        register_checkpoint_preview_route()
    except Exception:
        # Keep package import resilient when runtime web server is unavailable.
        pass

if register_autocomplete_routes is not None:
    try:
        register_autocomplete_routes()
    except Exception:
        # Keep package import resilient when runtime web server is unavailable.
        pass

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
