from nodes import CheckpointLoaderSimple, VAELoader, CLIPLoader
import folder_paths

from ..models import BubbaMetadata
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


def _vae_choices():
    return [_NONE_SENTINEL] + VAELoader.vae_list(VAELoader)


def _clip_choices():
    try:
        return [_NONE_SENTINEL] + folder_paths.get_filename_list("text_encoders")
    except Exception:
        return [_NONE_SENTINEL]


class BubbaComboLoader:
    """Loads a checkpoint plus optional external VAE and CLIP/text-encoder overrides
    in a single node.  Leave VAE or CLIP set to 'None' to use whatever was baked
    into the checkpoint."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ckpt_name": (folder_paths.get_filename_list("checkpoints"),),
                "vae_name": (_vae_choices(),),
                "clip_name": (_clip_choices(),),
                "clip_type": (_CLIP_TYPES,),
                "clip_skip": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 24,
                        "step": 1,
                        "tooltip": "Number of CLIP layers to skip (0 = disabled).",
                    },
                ),
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata object to update with model name."},
                ),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING", "BUBBA_METADATA")
    RETURN_NAMES = ("model", "clip", "vae", "checkpoint_name", "metadata")
    FUNCTION = "load"
    CATEGORY = "Bubba Nodes/Generation"
    DESCRIPTION = (
        "Loads a checkpoint and optionally overrides its baked-in VAE and CLIP with "
        "external files — useful for models like Anima/WAI-Anima that ship without "
        "an embedded text encoder or VAE. Applies optional CLIP skip. "
        "Set vae_name or clip_name to 'None' to use the checkpoint's built-in version."
    )

    def load(self, ckpt_name, vae_name, clip_name, clip_type, clip_skip, metadata=None):
        # --- Checkpoint ---------------------------------------------------------
        model, ckpt_clip, ckpt_vae = CheckpointLoaderSimple().load_checkpoint(ckpt_name)

        # --- VAE override -------------------------------------------------------
        if vae_name and vae_name != _NONE_SENTINEL:
            (vae,) = VAELoader().load_vae(vae_name)
        else:
            vae = ckpt_vae

        # --- CLIP/text-encoder override -----------------------------------------
        if clip_name and clip_name != _NONE_SENTINEL:
            (clip,) = CLIPLoader().load_clip(clip_name, type=clip_type)
        else:
            clip = ckpt_clip

        # --- Optional CLIP skip -------------------------------------------------
        applied_clip_skip = max(0, int(clip_skip or 0))
        if applied_clip_skip > 0:
            try:
                clip = clip.clone()
                clip.clip_layer(-applied_clip_skip)
            except Exception as exc:
                print(f"[Bubba] WARNING: Failed to apply CLIP skip={applied_clip_skip}. Using unmodified CLIP. Error: {exc}")
                applied_clip_skip = 0

        # --- Metadata -----------------------------------------------------------
        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            model_name=checkpoint_display_name(ckpt_name),
            clip_skip=applied_clip_skip,
        )

        return (model, clip, vae, str(ckpt_name), updated_metadata)
