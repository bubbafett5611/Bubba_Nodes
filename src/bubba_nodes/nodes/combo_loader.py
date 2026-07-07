import logging
from comfy_api.latest import IO

from ..compat.core_nodes import checkpoint_names, load_checkpoint, load_clip, load_vae, vae_names
from ..compat.paths import get_filename_list
from ..models import BubbaMetadata, BubbaPipe
from ..utils.checkpointing import checkpoint_display_name


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

_NONE_SENTINEL = "None (use checkpoint CLIP/VAE)"
logger = logging.getLogger("bubba_nodes")


def _vae_choices():
    return [_NONE_SENTINEL] + vae_names()


def _clip_choices():
    try:
        return [_NONE_SENTINEL] + get_filename_list("text_encoders")
    except Exception:
        return [_NONE_SENTINEL]


class BubbaComboLoader(IO.ComfyNode):
    """Loads a checkpoint plus optional external VAE and CLIP/text-encoder overrides
    in a single node.  Leave VAE or CLIP set to 'None' to use whatever was baked
    into the checkpoint."""

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaComboLoader",
            display_name="Bubba Combo Loader",
            category="Bubba Nodes/Generation",
            description="Loads a checkpoint with optional external VAE and CLIP overrides.",
            inputs=[
                IO.Combo.Input("ckpt_name", options=checkpoint_names()),
                IO.Combo.Input("clip_name", options=_clip_choices()),
                IO.Combo.Input("vae_name", options=_vae_choices()),
                IO.Combo.Input("clip_type", options=_CLIP_TYPES),
                IO.Int.Input("clip_skip", default=0, min=0, max=24),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Combo.Input("clip_device", options=["default", "cpu"], default="default", optional=True, advanced=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.Vae.Output("vae"),
                IO.String.Output("checkpoint_name"),
            ],
        )

    @classmethod
    def execute(cls, ckpt_name, clip_name, vae_name, clip_type, clip_skip, pipe=None, metadata=None, clip_device="default"):
        source_pipe = BubbaPipe.coerce(pipe)
        # --- Checkpoint ---------------------------------------------------------
        model, ckpt_clip, ckpt_vae = load_checkpoint(ckpt_name)

        # --- VAE override -------------------------------------------------------
        if vae_name and vae_name != _NONE_SENTINEL:
            vae = load_vae(vae_name)
        else:
            vae = ckpt_vae

        # --- CLIP/text-encoder override -----------------------------------------
        if clip_name and clip_name != _NONE_SENTINEL:
            clip = load_clip(clip_name, clip_type, clip_device or "default")
        else:
            clip = ckpt_clip

        # --- Optional CLIP skip -------------------------------------------------
        applied_clip_skip = max(0, int(clip_skip or 0))
        if applied_clip_skip > 0:
            try:
                clip = clip.clone()
                clip.clip_layer(-applied_clip_skip)
            except Exception as exc:
                logger.warning("Failed to apply CLIP skip=%s. Using unmodified CLIP. Error: %s", applied_clip_skip, exc)
                applied_clip_skip = 0

        # --- Metadata -----------------------------------------------------------
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            model_name=checkpoint_display_name(ckpt_name),
            clip_skip=applied_clip_skip,
        )
        updated_pipe = source_pipe.updated(
            model=model,
            clip=clip,
            vae=vae,
            positive=None,
            negative=None,
            metadata=updated_metadata,
        )

        return IO.NodeOutput(updated_pipe, updated_metadata, model, clip, vae, str(ckpt_name))
