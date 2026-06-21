from __future__ import annotations

from ..models import BubbaMetadata, BubbaPipe


class BubbaPipeIn:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe to update."}),
                "image": ("IMAGE", {"tooltip": "Optional image to store in the pipe."}),
                "mask": ("MASK", {"tooltip": "Optional mask to store in the pipe."}),
                "latent": ("LATENT", {"tooltip": "Optional latent to store in the pipe."}),
                "metadata": ("BUBBA_METADATA", {"tooltip": "Optional metadata to store in the pipe."}),
                "model": ("MODEL", {"tooltip": "Optional model to store in the pipe."}),
                "clip": ("CLIP", {"tooltip": "Optional CLIP to store in the pipe."}),
                "vae": ("VAE", {"tooltip": "Optional VAE to store in the pipe."}),
                "positive": ("CONDITIONING", {"tooltip": "Optional positive conditioning to store in the pipe."}),
                "negative": ("CONDITIONING", {"tooltip": "Optional negative conditioning to store in the pipe."}),
                "positive_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "positive"},
                        "tooltip": "Optional positive prompt text to store in the pipe when non-empty.",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Optional negative prompt text to store in the pipe when non-empty.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE",)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "build_pipe"
    CATEGORY = "Bubba Nodes/Pipe"
    DESCRIPTION = "Builds or updates a Bubba pipe from explicit socket values."

    def build_pipe(
        self,
        pipe=None,
        image=None,
        mask=None,
        latent=None,
        metadata=None,
        model=None,
        clip=None,
        vae=None,
        positive=None,
        negative=None,
        positive_prompt="",
        negative_prompt="",
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        changes = {}
        for key, value in {
            "image": image,
            "mask": mask,
            "latent": latent,
            "metadata": BubbaMetadata.coerce(metadata) if metadata is not None else None,
            "model": model,
            "clip": clip,
            "vae": vae,
            "positive": positive,
            "negative": negative,
        }.items():
            if value is not None:
                changes[key] = value

        positive_text = str(positive_prompt or "").strip()
        negative_text = str(negative_prompt or "").strip()
        if positive_text:
            changes["positive_prompt"] = positive_text
        if negative_text:
            changes["negative_prompt"] = negative_text

        return (source_pipe.updated(**changes),)
