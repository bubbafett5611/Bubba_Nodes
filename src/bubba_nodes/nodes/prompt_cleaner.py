from ..models import BubbaMetadata, BubbaPipe
from ..utils.prompting import empty_conditioning, encode_conditioning
from ..utils.prompt_analysis import normalize_prompt_csv


class BubbaPromptCleaner:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "positive"},
                        "tooltip": "Input positive prompt to clean.",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Input negative prompt to clean.",
                    },
                ),
                "cleanup": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Normalize spacing and separators.",
                    },
                ),
                "dedupe": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove duplicate tags while preserving order.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe to update with cleaned prompts."}),
                "metadata": ("BUBBA_METADATA", {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."}),
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "Optional CLIP to encode cleaned positive and negative conditioning outputs.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA", "CONDITIONING", "CONDITIONING", "STRING", "STRING")
    RETURN_NAMES = ("pipe", "metadata", "positive", "negative", "clean_positive", "clean_negative")
    FUNCTION = "clean_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Cleans positive and negative prompts and optionally encodes conditioning when CLIP is connected."

    def _normalize(self, text: str, cleanup: bool, dedupe: bool) -> str:
        return normalize_prompt_csv(text, cleanup=cleanup, dedupe=dedupe)

    def clean_prompt(self, positive_prompt, negative_prompt, cleanup, dedupe, pipe=None, metadata=None, clip=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_clip = clip if clip is not None else source_pipe.clip
        clean_positive = self._normalize(positive_prompt, cleanup, dedupe)
        clean_negative = self._normalize(negative_prompt, cleanup, dedupe)
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
        return (updated_pipe, updated_metadata, positive, negative, clean_positive, clean_negative)
