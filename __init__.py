"""Bubba Nodes ComfyUI extension entry point."""

__all__ = ["WEB_DIRECTORY", "comfy_entrypoint"]

__author__ = "BubbaNodes"
__email__ = "metalgfx@gmail.com"
__version__ = "3.0.0"

WEB_DIRECTORY = "./web"


async def comfy_entrypoint():
    from .src.bubba_nodes.nodes import comfy_entrypoint as node_entrypoint

    return await node_entrypoint()
