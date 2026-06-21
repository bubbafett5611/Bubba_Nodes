from __future__ import annotations

from ..models import BubbaPipe


class BubbaPipeOut:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Bubba pipe to unpack into visible sockets."}),
            },
        }

    RETURN_TYPES = (
        "BUBBA_PIPE",
        "IMAGE",
        "MASK",
        "LATENT",
        "BUBBA_METADATA",
        "MODEL",
        "CLIP",
        "VAE",
        "CONDITIONING",
        "CONDITIONING",
        "STRING",
        "STRING",
    )
    RETURN_NAMES = (
        "pipe",
        "image",
        "mask",
        "latent",
        "metadata",
        "model",
        "clip",
        "vae",
        "positive",
        "negative",
        "positive_prompt",
        "negative_prompt",
    )
    FUNCTION = "unpack_pipe"
    CATEGORY = "Bubba Nodes/Pipe"
    DESCRIPTION = "Unpacks a Bubba pipe into visible sockets for advanced graph wiring."

    def unpack_pipe(self, pipe):
        source_pipe = BubbaPipe.coerce(pipe)
        return (
            source_pipe,
            source_pipe.image,
            source_pipe.mask,
            source_pipe.latent,
            source_pipe.metadata,
            source_pipe.model,
            source_pipe.clip,
            source_pipe.vae,
            source_pipe.positive,
            source_pipe.negative,
            source_pipe.positive_prompt,
            source_pipe.negative_prompt,
        )
