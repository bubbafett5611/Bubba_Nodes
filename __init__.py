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


def _warn_optional_feature_failure(feature_name: str, error: Exception) -> None:
    print(f"[Bubba] WARNING: {feature_name} unavailable. Error: {error}")


def _register_optional_route(route_name: str, register_route) -> None:
    try:
        register_route()
    except Exception as error:
        _warn_optional_feature_failure(route_name, error)


def _register_optional_web_routes() -> None:
    try:
        from .src.bubba_nodes.server import (
            register_checkpoint_preview_route,
            register_autocomplete_routes,
        )
    except Exception as error:
        _warn_optional_feature_failure("web routes", error)
        return

    _register_optional_route("checkpoint preview route", register_checkpoint_preview_route)
    _register_optional_route("autocomplete routes", register_autocomplete_routes)


_register_optional_web_routes()

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
