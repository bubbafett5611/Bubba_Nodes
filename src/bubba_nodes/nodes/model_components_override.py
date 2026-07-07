from __future__ import annotations

import logging

from comfy_api.latest import IO

from ..compat.core_nodes import load_clip, load_vae, vae_names
from ..compat.paths import get_filename_list
from ..models import BubbaPipe
from ..models.pipe import resolve_pipe_value


_CLIP_TYPES = [
    "stable_diffusion",
    "stable_cascade",
    "sd3",
    "stable_audio",
    "mochi",
    "ltxv",
    "pixart",
    "cosmos",
    "lumina2",
    "wan",
    "hidream",
    "chroma",
    "ace",
    "omnigen2",
    "qwen_image",
    "hunyuan_image",
    "flux2",
    "ovis",
    "longcat_image",
]
_KEEP_PIPE_COMPONENT = "None (keep pipe component)"
logger = logging.getLogger("bubba_nodes")


def _clip_choices() -> list[str]:
    return [_KEEP_PIPE_COMPONENT, *get_filename_list("text_encoders")]


def _vae_choices() -> list[str]:
    return [_KEEP_PIPE_COMPONENT, *vae_names()]


class BubbaModelComponentsOverride(IO.ComfyNode):
    """Replace CLIP and/or VAE components carried by an existing pipe."""

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaModelComponentsOverride",
            display_name="Bubba Model Components Override",
            category="Bubba Nodes/Generation",
            description="Optionally replaces a pipe's CLIP/text encoder and VAE, then applies CLIP skip.",
            inputs=[
                pipe.Input("pipe"),
                IO.Combo.Input("clip_name", options=_clip_choices(), default=_KEEP_PIPE_COMPONENT),
                IO.Combo.Input("vae_name", options=_vae_choices(), default=_KEEP_PIPE_COMPONENT),
                IO.Combo.Input("clip_type", options=_CLIP_TYPES, default="stable_diffusion"),
                IO.Int.Input("clip_skip", default=0, min=0, max=24),
                IO.Combo.Input("clip_device", options=["default", "cpu"], default="default"),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.Vae.Output("vae"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(
        cls,
        pipe,
        clip_name=_KEEP_PIPE_COMPONENT,
        vae_name=_KEEP_PIPE_COMPONENT,
        clip_type="stable_diffusion",
        clip_skip=0,
        clip_device="default",
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        # A model is intentionally optional here so this node can prepare CLIP/VAE
        # on a partial pipe before a checkpoint or comparison loader supplies it.
        model = source_pipe.model
        clip_replaced = bool(clip_name and clip_name != _KEEP_PIPE_COMPONENT)
        vae_replaced = bool(vae_name and vae_name != _KEEP_PIPE_COMPONENT)
        clip = load_clip(clip_name, clip_type, clip_device or "default") if clip_replaced else source_pipe.clip
        vae = load_vae(vae_name) if vae_replaced else source_pipe.vae
        clip = resolve_pipe_value(None, clip, "clip")
        vae = resolve_pipe_value(None, vae, "vae")

        applied_clip_skip = max(0, int(clip_skip or 0))
        if applied_clip_skip > 0:
            try:
                clip = clip.clone()
                clip.clip_layer(-applied_clip_skip)
            except Exception as error:
                logger.warning("Failed to apply CLIP skip=%s. Using unmodified CLIP. Error: %s", applied_clip_skip, error)
                applied_clip_skip = 0

        metadata = source_pipe.metadata.updated(clip_skip=applied_clip_skip)
        updated_pipe = source_pipe.updated(
            model=model,
            clip=clip,
            vae=vae,
            positive=None,
            negative=None,
            metadata=metadata,
        )
        clip_status = str(clip_name) if clip_replaced else "pipe CLIP"
        vae_status = str(vae_name) if vae_replaced else "pipe VAE"
        model_status = "present" if model is not None else "pending downstream loader"
        info = f"Model: {model_status}\nCLIP: {clip_status} ({clip_type}, skip {applied_clip_skip}, {clip_device})\nVAE: {vae_status}"
        return IO.NodeOutput(updated_pipe, metadata, model, clip, vae, info)
