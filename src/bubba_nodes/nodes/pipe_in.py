from __future__ import annotations

from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe

BUBBA_PIPE = IO.Custom("BUBBA_PIPE")
BUBBA_METADATA = IO.Custom("BUBBA_METADATA")


class BubbaPipeIn(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaPipeIn",
            display_name="Bubba Pipe In",
            category="Bubba Nodes/Pipe",
            description="Builds or updates a Bubba pipe from explicit socket values.",
            inputs=[
                BUBBA_PIPE.Input("pipe", optional=True, tooltip="Optional incoming pipe to update."),
                IO.Image.Input("image", optional=True),
                IO.Mask.Input("mask", optional=True),
                IO.Latent.Input("latent", optional=True),
                BUBBA_METADATA.Input("metadata", optional=True),
                IO.Model.Input("model", optional=True),
                IO.Clip.Input("clip", optional=True),
                IO.Vae.Input("vae", optional=True),
                IO.Conditioning.Input("positive", optional=True),
                IO.Conditioning.Input("negative", optional=True),
                IO.String.Input(
                    "positive_prompt", default="", multiline=True, optional=True, extra_dict={"bubba.autocomplete": {"group": "positive"}}
                ),
                IO.String.Input(
                    "negative_prompt", default="", multiline=True, optional=True, extra_dict={"bubba.autocomplete": {"group": "negative"}}
                ),
            ],
            outputs=[BUBBA_PIPE.Output("pipe")],
        )

    @classmethod
    def execute(
        cls,
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

        return IO.NodeOutput(source_pipe.updated(**changes))
