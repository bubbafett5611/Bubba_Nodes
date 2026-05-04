from ..utils.prompting import clean_prompt_value, dedupe_prompt_tokens, split_prompt_tokens
from ..utils.prompt_analysis import find_duplicate_prompt_tokens, find_pair_conflicts


class BubbaPromptInspector:
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
                        "tooltip": "Positive prompt text to inspect.",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Negative prompt text to inspect.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("INT", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("token_count", "duplicate_tags", "conflict_warnings", "formatted_preview")
    FUNCTION = "inspect_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Analyzes positive/negative prompts for token count, duplicates, conflicts, and cleaned preview text."

    @staticmethod
    def _clean_parts(text: str) -> list[str]:
        parts = split_prompt_tokens(text)
        cleaned = [clean_prompt_value(part) for part in parts]
        return [part for part in cleaned if part]

    def inspect_prompt(self, positive_prompt, negative_prompt):
        # TODO(optimize): Add optional fast-path mode that skips duplicate and conflict checks for very long prompts.
        positive_parts = self._clean_parts(positive_prompt)
        negative_parts = self._clean_parts(negative_prompt)

        token_count = len(positive_parts) + len(negative_parts)

        positive_duplicates = find_duplicate_prompt_tokens(positive_parts)
        negative_duplicates = find_duplicate_prompt_tokens(negative_parts)
        duplicate_lines: list[str] = []
        if positive_duplicates:
            duplicate_lines.append(f"positive: {', '.join(positive_duplicates)}")
        if negative_duplicates:
            duplicate_lines.append(f"negative: {', '.join(negative_duplicates)}")
        duplicate_tags = "\n".join(duplicate_lines) if duplicate_lines else "none"

        positive_set = {part.lower() for part in positive_parts}
        negative_set = {part.lower() for part in negative_parts}
        cross_conflicts = sorted(positive_set.intersection(negative_set))

        warning_lines: list[str] = []
        if cross_conflicts:
            warning_lines.append(f"present in both positive and negative: {', '.join(cross_conflicts)}")
        positive_pair_conflicts = find_pair_conflicts(positive_parts)
        if positive_pair_conflicts:
            warning_lines.append(f"positive pair conflicts: {', '.join(positive_pair_conflicts)}")
        negative_pair_conflicts = find_pair_conflicts(negative_parts)
        if negative_pair_conflicts:
            warning_lines.append(f"negative pair conflicts: {', '.join(negative_pair_conflicts)}")
        conflict_warnings = "\n".join(warning_lines) if warning_lines else "none"

        formatted_positive = ", ".join(dedupe_prompt_tokens(positive_parts))
        formatted_negative = ", ".join(dedupe_prompt_tokens(negative_parts))
        formatted_preview = f"Positive: {formatted_positive}\n\n" f"Negative: {formatted_negative}\n\n" f"Token count: {token_count}"

        return (token_count, duplicate_tags, conflict_warnings, formatted_preview)
