from __future__ import annotations

import torch
from comfy_api.latest import IO

from ..compat.core_nodes import checkpoint_names, load_checkpoint
from ..models import BubbaPipe
from ..utils.checkpointing import checkpoint_display_name


_NONE_MODEL = "None"


def _fork_latent(value):
    if isinstance(value, torch.Tensor):
        return value.clone()
    if isinstance(value, dict):
        return {key: _fork_latent(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_fork_latent(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_fork_latent(item) for item in value)
    return value


class BubbaModelCompareLoader(IO.ComfyNode):
    """Load four checkpoints into independent generation pipes."""

    @classmethod
    def define_schema(cls):
        pipe = IO.Custom("BUBBA_PIPE")
        checkpoints = checkpoint_names()
        choices = [_NONE_MODEL, *(name for name in checkpoints if name != _NONE_MODEL)]
        first_model = choices[1] if len(choices) > 1 else _NONE_MODEL
        return IO.Schema(
            node_id="BubbaModelCompareLoader",
            display_name="Bubba Model Compare Loader",
            category="Bubba Nodes/Generation",
            description="Forks an optional source pipe and loads four checkpoints into separate comparison pipes.",
            inputs=[
                pipe.Input("pipe", optional=True),
                IO.Combo.Input("model_1", options=choices, default=first_model),
                IO.Combo.Input("model_2", options=choices, default=_NONE_MODEL),
                IO.Combo.Input("model_3", options=choices, default=_NONE_MODEL),
                IO.Combo.Input("model_4", options=choices, default=_NONE_MODEL),
                IO.Boolean.Input("replace_clip", default=True),
                IO.Boolean.Input("replace_vae", default=True),
            ],
            outputs=[
                pipe.Output("pipe_1"),
                pipe.Output("pipe_2"),
                pipe.Output("pipe_3"),
                pipe.Output("pipe_4"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(cls, model_1, model_2, model_3, model_4, replace_clip=True, replace_vae=True, pipe=None):
        source_pipe = BubbaPipe.coerce(pipe)
        names = [model_1, model_2, model_3, model_4]
        if not any(name and name != _NONE_MODEL for name in names):
            raise ValueError("Bubba Model Compare Loader needs at least one selected model.")
        pipes = []
        display_names = []
        for checkpoint_name in names:
            if not checkpoint_name or checkpoint_name == _NONE_MODEL:
                pipes.append(
                    source_pipe.updated(
                        model=None,
                        positive=None if replace_clip else source_pipe.positive,
                        negative=None if replace_clip else source_pipe.negative,
                        latent=_fork_latent(source_pipe.latent),
                        metadata=source_pipe.metadata.updated(model_name=""),
                    )
                )
                continue
            model, checkpoint_clip, checkpoint_vae = load_checkpoint(checkpoint_name)
            clip = checkpoint_clip if replace_clip else source_pipe.clip
            vae = checkpoint_vae if replace_vae else source_pipe.vae
            if clip is None:
                raise ValueError("CLIP replacement is disabled, but the incoming pipe has no CLIP.")
            if vae is None:
                raise ValueError("VAE replacement is disabled, but the incoming pipe has no VAE.")
            display_name = checkpoint_display_name(checkpoint_name)
            metadata = source_pipe.metadata.updated(model_name=display_name)
            pipes.append(
                source_pipe.updated(
                    model=model,
                    clip=clip,
                    vae=vae,
                    positive=None if replace_clip else source_pipe.positive,
                    negative=None if replace_clip else source_pipe.negative,
                    latent=_fork_latent(source_pipe.latent),
                    metadata=metadata,
                )
            )
            display_names.append(display_name)

        info = "Loaded model comparison: " + " | ".join(display_names)
        return IO.NodeOutput(*pipes, info)
