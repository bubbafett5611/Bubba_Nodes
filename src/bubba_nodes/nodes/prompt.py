from ..utils.prompting import (
    assemble_prompt_sections,
    build_prompts_from_sections,
    clean_prompt_value,
    dedupe_prompt_tokens,
    empty_conditioning,
    encode_conditioning,
    format_positive_prompt,
    split_prompt_tokens,
)

# TODO(new-node): Add a prompt preset library node that can load/save reusable section sets by character or scene.
# TODO(new-feature): Add token-budget guidance output (per-model limits) to warn before conditioning truncation.


def _find_duplicates(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    dup_seen: set[str] = set()
    for part in parts:
        key = part.lower()
        if key in seen and key not in dup_seen:
            duplicates.append(part)
            dup_seen.add(key)
            continue
        seen.add(key)
    return duplicates


def _conflict_pairs() -> tuple[tuple[str, str], ...]:
    # TODO(optimize): Move conflict pairs to a config file so users can tune rules without code edits.
    # Keep this list concise and practical for prompt quality checks.
    return (
        ("solo", "multiple people"),
        ("male", "female"),
        ("day", "night"),
        ("indoors", "outdoors"),
        ("safe", "nsfw"),
    )


def _find_pair_conflicts(parts: list[str]) -> list[str]:
    normalized = {part.strip().lower() for part in parts if part.strip()}
    warnings: list[str] = []
    for left, right in _conflict_pairs():
        if left in normalized and right in normalized:
            warnings.append(f"{left} <-> {right}")
    return warnings


def _build_prompts_from_sections(
    sections: dict[str, str],
    cleanup: bool,
    dedupe: bool,
    include_character_in_positive: bool = True,
) -> tuple[str, str, str]:
    return build_prompts_from_sections(
        sections,
        cleanup=cleanup,
        dedupe=dedupe,
        include_character_in_positive=include_character_in_positive,
    )

class BubbaCharacterPromptBuilder:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "CLIP used to encode positive and negative conditioning outputs.",
                    },
                ),
                "appearance": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "appearance"},
                        "tooltip": "Face, hair, age, and identifying visual traits.",
                    },
                ),
                "body": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "body"},
                        "tooltip": "Body proportions, physique, and anatomy descriptors.",
                    },
                ),
                "clothing": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "clothing"},
                        "tooltip": "Outfit, accessories, and materials.",
                    },
                ),
                "pose": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "pose"},
                        "tooltip": "Body pose and camera-facing orientation.",
                    },
                ),
                "expression": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "expression"},
                        "tooltip": "Facial expression and emotion.",
                    },
                ),
                "scene": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "scene"},
                        "tooltip": "Environment, lighting, and composition context.",
                    },
                ),
                "style_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "style"},
                        "tooltip": "Style and rendering tags, comma-separated.",
                    },
                ),
                "quality_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "quality"},
                        "tooltip": "Quality/detail tags, comma-separated.",
                    },
                ),
                "negative_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "bubba.autocomplete": {"group": "negative"},
                        "tooltip": "Negative prompt tags, comma-separated.",
                    },
                ),
                "format_mode": (
                    ["booru", "prose", "hybrid"],
                    {
                        "default": "hybrid",
                        "tooltip": "Prompt formatting style for positive output.",
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
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "sections", "positive_conditioning", "negative_conditioning")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Builds positive/negative prompts from character sections and encodes conditioning with CLIP."

    @staticmethod
    def _clean_value(text: str) -> str:
        return clean_prompt_value(text)

    @staticmethod
    def _split_tokens(text: str) -> list[str]:
        return split_prompt_tokens(text)

    @staticmethod
    def _dedupe_tokens(items: list[str]) -> list[str]:
        return dedupe_prompt_tokens(items)

    def _format_positive(self, values: list[str], format_mode: str) -> str:
        return format_positive_prompt(values, format_mode)

    def build_prompt(
        self,
        clip,
        appearance,
        body,
        clothing,
        pose,
        expression,
        scene,
        style_tags,
        quality_tags,
        negative_tags,
        format_mode,
        cleanup,
        dedupe,
    ):
        sections = assemble_prompt_sections(
            appearance=appearance,
            body=body,
            clothing=clothing,
            pose=pose,
            expression=expression,
            scene=scene,
            style_tags=style_tags,
            quality_tags=quality_tags,
            negative_tags=negative_tags,
            format_mode=format_mode,
        )
        positive_prompt, negative_prompt, sections_text = _build_prompts_from_sections(
            sections,
            cleanup=cleanup,
            dedupe=dedupe,
            include_character_in_positive=False,
        )
        positive_conditioning = encode_conditioning(clip, positive_prompt)
        negative_conditioning = encode_conditioning(clip, negative_prompt)
        return (positive_prompt, negative_prompt, sections_text, positive_conditioning, negative_conditioning)


class BubbaPromptCleaner:
    @classmethod
    def INPUT_TYPES(s):
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
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Cleans positive and negative prompts and optionally encodes conditioning when CLIP is connected."

    def _normalize(self, text: str, cleanup: bool, dedupe: bool) -> str:
        parts = BubbaCharacterPromptBuilder._split_tokens(text)
        if cleanup:
            parts = [BubbaCharacterPromptBuilder._clean_value(item) for item in parts]
            parts = [item for item in parts if item]
        if dedupe:
            parts = BubbaCharacterPromptBuilder._dedupe_tokens(parts)
        return ", ".join(parts)

    @staticmethod
    def _empty_conditioning():
        return empty_conditioning()

    def clean_prompt(self, positive_prompt, negative_prompt, cleanup, dedupe, clip=None):
        clean_positive = self._normalize(positive_prompt, cleanup, dedupe)
        clean_negative = self._normalize(negative_prompt, cleanup, dedupe)
        if clip is None:
            return (clean_positive, clean_negative, self._empty_conditioning(), self._empty_conditioning())
        return (
            clean_positive,
            clean_negative,
            encode_conditioning(clip, clean_positive),
            encode_conditioning(clip, clean_negative),
        )


class BubbaPromptInspector:
    @classmethod
    def INPUT_TYPES(s):
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
    CATEGORY = "Bubba Nodes"
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

        positive_duplicates = _find_duplicates(positive_parts)
        negative_duplicates = _find_duplicates(negative_parts)
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
        positive_pair_conflicts = _find_pair_conflicts(positive_parts)
        if positive_pair_conflicts:
            warning_lines.append(f"positive pair conflicts: {', '.join(positive_pair_conflicts)}")
        negative_pair_conflicts = _find_pair_conflicts(negative_parts)
        if negative_pair_conflicts:
            warning_lines.append(f"negative pair conflicts: {', '.join(negative_pair_conflicts)}")
        conflict_warnings = "\n".join(warning_lines) if warning_lines else "none"

        formatted_positive = ", ".join(dedupe_prompt_tokens(positive_parts))
        formatted_negative = ", ".join(dedupe_prompt_tokens(negative_parts))
        formatted_preview = (
            f"Positive: {formatted_positive}\n\n"
            f"Negative: {formatted_negative}\n\n"
            f"Token count: {token_count}"
        )

        return (token_count, duplicate_tags, conflict_warnings, formatted_preview)


