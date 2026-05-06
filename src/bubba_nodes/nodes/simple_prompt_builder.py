from ..models import BubbaMetadata
from ..utils.prompting import (
    clean_prompt_value,
    split_prompt_tokens,
    dedupe_prompt_tokens,
    encode_conditioning,
)


class BubbaSimplePromptBuilder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "CLIP used to encode positive and negative conditioning outputs.",
                    },
                ),
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
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object to update with the built prompts.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "CONDITIONING", "CONDITIONING", "BUBBA_METADATA")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "positive_conditioning", "negative_conditioning", "metadata")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Builds a positive/negative prompt from single text inputs with optional cleanup and deduplication."

    def build_prompt(self, clip, positive, negative, cleanup, dedupe, metadata=None):
        positive_prompt = self._process(positive, cleanup, dedupe)
        negative_prompt = self._process(negative, cleanup, dedupe)

        positive_conditioning = encode_conditioning(clip, positive_prompt)
        negative_conditioning = encode_conditioning(clip, negative_prompt)

        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )

        return (positive_prompt, negative_prompt, positive_conditioning, negative_conditioning, updated_metadata)

    def _process(self, text: str, cleanup: bool, dedupe: bool) -> str:
        if cleanup:
            text = clean_prompt_value(text)
        if dedupe:
            tokens = split_prompt_tokens(text)
            tokens = dedupe_prompt_tokens(tokens)
            text = ", ".join(tokens)
        return text
