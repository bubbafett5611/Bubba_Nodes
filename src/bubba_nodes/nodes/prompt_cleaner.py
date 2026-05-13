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
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "Optional CLIP to encode cleaned positive and negative conditioning outputs.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("clean_positive", "clean_negative", "positive_conditioning", "negative_conditioning")
    FUNCTION = "clean_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Cleans positive and negative prompts and optionally encodes conditioning when CLIP is connected."

    def _normalize(self, text: str, cleanup: bool, dedupe: bool) -> str:
        return normalize_prompt_csv(text, cleanup=cleanup, dedupe=dedupe)

    def clean_prompt(self, positive_prompt, negative_prompt, cleanup, dedupe, clip=None):
        clean_positive = self._normalize(positive_prompt, cleanup, dedupe)
        clean_negative = self._normalize(negative_prompt, cleanup, dedupe)
        if clip is None:
            return (clean_positive, clean_negative, empty_conditioning(), empty_conditioning())
        return (
            clean_positive,
            clean_negative,
            encode_conditioning(clip, clean_positive),
            encode_conditioning(clip, clean_negative),
        )
