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
