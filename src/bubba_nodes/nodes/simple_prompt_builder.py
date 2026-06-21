from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.prompting import (
    clean_prompt_value,
    split_prompt_tokens,
    dedupe_prompt_tokens,
    encode_conditioning,
)
from ..utils.prompt_expansion import PromptExpansionResult, expand_prompt_text


class BubbaSimplePromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {},
                        "tooltip": "Positive prompt tags, comma-separated.",
                    },
                ),
                "negative": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Negative prompt tags, comma-separated.",
                    },
                ),
                "cleanup": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Normalize spacing and trim separators.",
                    },
                ),
                "dedupe": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove duplicate tags while preserving first occurrence order.",
                    },
                ),
                "prompt_seed": (
                    "INT",
                    {
                        "default": -1,
                        "min": -1,
                        "max": 2**32 - 1,
                        "step": 1,
                        "control_after_generate": True,
                        "tooltip": "Seed for wildcards and inline choices. -1 inherits metadata.seed, then falls back to 0.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing the CLIP to use."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata override. Overrides pipe.metadata when connected.",
                    },
                ),
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "Optional CLIP override. Overrides pipe.clip when connected.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "CONDITIONING", "CONDITIONING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "positive", "negative", "positive_prompt", "negative_prompt", "expansion_report")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = (
        "Builds positive/negative prompts with deterministic {a|b} choices and __file__ wildcards, "
        "then optionally cleans, deduplicates, and encodes them."
    )

    def build_prompt(self, positive, negative, cleanup, dedupe, prompt_seed=-1, pipe=None, metadata=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = resolve_pipe_value(clip, source_pipe.clip, "clip")
        source_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        expansion_seed = int(prompt_seed) if int(prompt_seed) >= 0 else int(source_metadata.seed or 0)
        positive_expansion = expand_prompt_text(positive, seed=expansion_seed, field_name="positive")
        negative_expansion = expand_prompt_text(negative, seed=expansion_seed, field_name="negative")
        positive_prompt = self._process(positive_expansion.resolved_text, cleanup, dedupe)
        negative_prompt = self._process(negative_expansion.resolved_text, cleanup, dedupe)

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

        expansion_report = self._format_expansion_report(
            positive_expansion,
            negative_expansion,
            positive_prompt,
            negative_prompt,
        )
        return (
            updated_pipe,
            updated_metadata,
            positive_conditioning,
            negative_conditioning,
            positive_prompt,
            negative_prompt,
            expansion_report,
        )

    def _process(self, text: str, cleanup: bool, dedupe: bool) -> str:
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
