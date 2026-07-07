from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..utils.prompting import empty_conditioning, encode_conditioning
from ..utils.prompt_analysis import normalize_prompt_csv


class BubbaPromptCleaner(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaPromptCleaner",
            display_name="Bubba Prompt Cleaner",
            category="Bubba Nodes/Prompt",
            description="Cleans prompts and optionally encodes conditioning when CLIP is connected.",
            inputs=[
                IO.String.Input("positive_prompt", default="", multiline=True, extra_dict={"bubba.autocomplete": {"group": "positive"}}),
                IO.String.Input("negative_prompt", default="", multiline=True, extra_dict={"bubba.autocomplete": {"group": "negative"}}),
                IO.Boolean.Input("cleanup", default=True),
                IO.Boolean.Input("dedupe", default=True),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Clip.Input("clip", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("clean_positive"),
                IO.String.Output("clean_negative"),
            ],
        )

    @staticmethod
    def _normalize(text: str, cleanup: bool, dedupe: bool) -> str:
        return normalize_prompt_csv(text, cleanup=cleanup, dedupe=dedupe)

    @classmethod
    def execute(cls, positive_prompt, negative_prompt, cleanup, dedupe, pipe=None, metadata=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = clip if clip is not None else source_pipe.clip
        clean_positive = cls._normalize(positive_prompt, cleanup, dedupe)
        clean_negative = cls._normalize(negative_prompt, cleanup, dedupe)
        if resolved_clip is None:
            positive = empty_conditioning()
            negative = empty_conditioning()
        else:
            positive = encode_conditioning(resolved_clip, clean_positive)
            negative = encode_conditioning(resolved_clip, clean_negative)
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            positive_prompt=clean_positive,
            negative_prompt=clean_negative,
        )
        updated_pipe = source_pipe.updated(
            clip=resolved_clip,
            positive=positive,
            negative=negative,
            positive_prompt=clean_positive,
            negative_prompt=clean_negative,
            metadata=updated_metadata,
        )
        return IO.NodeOutput(updated_pipe, updated_metadata, positive, negative, clean_positive, clean_negative)
