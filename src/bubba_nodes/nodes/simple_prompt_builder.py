from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.prompting import (
    clean_prompt_value,
    split_prompt_tokens,
    dedupe_prompt_tokens,
    encode_conditioning,
)
from ..utils.prompt_expansion import PromptExpansionResult, expand_prompt_text


class BubbaSimplePromptBuilder(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaSimplePromptBuilder",
            display_name="Bubba Simple Prompt Builder",
            category="Bubba Nodes/Prompt",
            description="Builds prompts with deterministic choices and wildcards, then cleans and encodes them.",
            inputs=[
                IO.String.Input("positive", default="", multiline=True, extra_dict={"bubba.autocomplete": {}}),
                IO.String.Input("negative", default="", multiline=True, extra_dict={"bubba.autocomplete": {"group": "negative"}}),
                IO.Boolean.Input("cleanup", default=True),
                IO.Boolean.Input("dedupe", default=True),
                IO.Int.Input("prompt_seed", default=-1, min=-1, max=2**32 - 1, control_after_generate=True),
                pipe.Input("pipe", optional=True),
                metadata.Input("metadata", optional=True),
                IO.Clip.Input("clip", optional=True),
            ],
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("positive_prompt"),
                IO.String.Output("negative_prompt"),
                IO.String.Output("expansion_report"),
            ],
        )

    @classmethod
    def execute(cls, positive, negative, cleanup, dedupe, prompt_seed=-1, pipe=None, metadata=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
        source_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        expansion_seed = int(prompt_seed) if int(prompt_seed) >= 0 else int(source_metadata.seed or 0)
        positive_expansion = expand_prompt_text(positive, seed=expansion_seed, field_name="positive")
        negative_expansion = expand_prompt_text(negative, seed=expansion_seed, field_name="negative")
        positive_prompt = cls._process(positive_expansion.resolved_text, cleanup, dedupe)
        negative_prompt = cls._process(negative_expansion.resolved_text, cleanup, dedupe)

        positive_conditioning = encode_conditioning(resolved_clip, positive_prompt)
        negative_conditioning = encode_conditioning(resolved_clip, negative_prompt)

        updated_metadata = source_metadata.updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
        updated_pipe = source_pipe.updated(
            clip=resolved_clip,
            positive=positive_conditioning,
            negative=negative_conditioning,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            metadata=updated_metadata,
        )

        expansion_report = cls._format_expansion_report(
            positive_expansion,
            negative_expansion,
            positive_prompt,
            negative_prompt,
        )
        return IO.NodeOutput(
            updated_pipe,
            updated_metadata,
            positive_conditioning,
            negative_conditioning,
            positive_prompt,
            negative_prompt,
            expansion_report,
        )

    @staticmethod
    def _process(text: str, cleanup: bool, dedupe: bool) -> str:
        if cleanup:
            text = clean_prompt_value(text)
        if dedupe:
            tokens = split_prompt_tokens(text)
            tokens = dedupe_prompt_tokens(tokens)
            text = ", ".join(tokens)
        return text

    @staticmethod
    def _format_expansion_report(
        positive: PromptExpansionResult,
        negative: PromptExpansionResult,
        final_positive: str,
        final_negative: str,
    ) -> str:
        sections = [
            positive.format_report("Positive"),
            f"Positive final: {final_positive}",
            negative.format_report("Negative"),
            f"Negative final: {final_negative}",
        ]
        return "\n\n".join(sections)
