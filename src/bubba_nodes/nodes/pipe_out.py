from __future__ import annotations

from comfy_api.latest import IO

from ..models import BubbaPipe

BUBBA_PIPE = IO.Custom("BUBBA_PIPE")
BUBBA_METADATA = IO.Custom("BUBBA_METADATA")


class BubbaPipeOut(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaPipeOut",
            display_name="Bubba Pipe Out",
            category="Bubba Nodes/Pipe",
            description="Unpacks a Bubba pipe into visible sockets for advanced graph wiring.",
            inputs=[BUBBA_PIPE.Input("pipe", tooltip="Bubba pipe to unpack into visible sockets.")],
            outputs=[
                BUBBA_PIPE.Output("pipe"),
                IO.Image.Output("image"),
                IO.Mask.Output("mask"),
                IO.Latent.Output("latent"),
                BUBBA_METADATA.Output("metadata"),
                IO.Model.Output("model"),
                IO.Clip.Output("clip"),
                IO.Vae.Output("vae"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("positive_prompt"),
                IO.String.Output("negative_prompt"),
            ],
        )

    @classmethod
    def execute(cls, pipe):
        source_pipe = BubbaPipe.coerce(pipe)
        return IO.NodeOutput(
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
