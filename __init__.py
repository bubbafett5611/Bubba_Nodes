"""Top-level package for bubba_nodes."""

import logging

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "UNAVAILABLE_NODE_MAPPINGS",
    "WEB_DIRECTORY",
]

__author__ = """BubbaNodes"""
__email__ = "metalgfx@gmail.com"
__version__ = "1.0.0"

logger = logging.getLogger("bubba_nodes")


def _warn_optional_feature_failure(feature_name: str, error: Exception) -> None:
    logger.warning("%s unavailable: %s", feature_name, error)


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

try:
    from .src.bubba_nodes.nodes import NODE_CLASS_MAPPINGS
    from .src.bubba_nodes.nodes import NODE_DISPLAY_NAME_MAPPINGS
    from .src.bubba_nodes.nodes import UNAVAILABLE_NODE_MAPPINGS
except Exception:
    logger.exception("Bubba Nodes failed during package registration.")
    raise

WEB_DIRECTORY = "./web"
