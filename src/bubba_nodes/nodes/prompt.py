import json
from pathlib import Path
import re


_SPLIT_RE = re.compile(r"\s*,\s*")
_MULTI_SPACE_RE = re.compile(r"\s+")

_SECTION_KEYS = [
    "character",
    "appearance",
    "body",
    "clothing",
    "pose",
    "expression",
    "scene",
    "style",
    "quality",
    "negative",
    "format_mode",
]

_POSITIVE_SECTION_KEYS = [
    "character",
    "appearance",
    "body",
    "clothing",
    "pose",
    "expression",
    "scene",
    "style",
    "quality",
]


def _default_sections() -> dict[str, str]:
    return {
        "character": "",
        "appearance": "",
        "body": "",
        "clothing": "",
        "pose": "",
        "expression": "",
        "scene": "",
        "style": "",
        "quality": "",
        "negative": "",
        "format_mode": "hybrid",
    }


def _presets_file_path() -> Path:
    # prompt.py -> nodes -> bubba_nodes -> src -> repo root
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "prompt_presets.json"


def _read_presets_file() -> dict[str, dict[str, str]]:
    path = _presets_file_path()
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(payload, dict):
        return {}

    raw_presets = payload.get("presets", payload)
    if not isinstance(raw_presets, dict):
        return {}

    presets: dict[str, dict[str, str]] = {}
    for name, value in raw_presets.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        merged = _default_sections()
        for key in _SECTION_KEYS:
            item = value.get(key, "")
            merged[key] = "" if item is None else str(item)
        presets[name] = merged
    return presets


def _write_presets_file(presets: dict[str, dict[str, str]]) -> None:
    path = _presets_file_path()
    payload = {
        "presets": presets,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sections_to_text(sections: dict[str, str]) -> str:
    lines = [f"{key}: {sections.get(key, '')}" for key in _SECTION_KEYS]
    return "\n".join(lines)


def _parse_sections_text(sections_text: str) -> dict[str, str]:
    sections = _default_sections()
    for raw_line in (sections_text or "").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key not in sections:
            continue
        sections[key] = value.strip()

    format_mode = sections.get("format_mode", "hybrid")
    if format_mode not in ("booru", "prose", "hybrid"):
        sections["format_mode"] = "hybrid"
    return sections


def _clean_section_value(value: str, cleanup: bool) -> str:
    if cleanup:
        return BubbaCharacterPromptBuilder._clean_value(value)
    return (value or "").strip()


def _build_prompts_from_sections(sections: dict[str, str], cleanup: bool, dedupe: bool) -> tuple[str, str, str]:
    normalized = _default_sections()
    normalized.update(sections)

    format_mode = normalized.get("format_mode", "hybrid")
    if format_mode not in ("booru", "prose", "hybrid"):
        format_mode = "hybrid"
        normalized["format_mode"] = format_mode

    positive_tokens = []
    section_lines = []

    for key in _POSITIVE_SECTION_KEYS:
        value = _clean_section_value(normalized.get(key, ""), cleanup)
        normalized[key] = value
        if value:
            parts = BubbaCharacterPromptBuilder._split_tokens(value)
            if dedupe:
                parts = BubbaCharacterPromptBuilder._dedupe_tokens(parts)
            value = ", ".join(parts)
            normalized[key] = value
            positive_tokens.extend(parts)
        section_lines.append(f"{key}: {normalized[key]}")

    negative_value = _clean_section_value(normalized.get("negative", ""), cleanup)
    negative_parts = BubbaCharacterPromptBuilder._split_tokens(negative_value)
    if cleanup:
        negative_parts = [BubbaCharacterPromptBuilder._clean_value(item) for item in negative_parts if BubbaCharacterPromptBuilder._clean_value(item)]
    if dedupe:
        negative_parts = BubbaCharacterPromptBuilder._dedupe_tokens(negative_parts)
    normalized["negative"] = ", ".join(negative_parts)

    if dedupe:
        positive_tokens = BubbaCharacterPromptBuilder._dedupe_tokens(positive_tokens)

    formatter = BubbaCharacterPromptBuilder()
    positive_prompt = formatter._format_positive(positive_tokens, format_mode)

    section_lines.append(f"negative: {normalized['negative']}")
    section_lines.append(f"format_mode: {normalized['format_mode']}")
    sections_text = "\n".join(section_lines)

    return (positive_prompt, normalized["negative"], sections_text)


class BubbaCharacterPromptBuilder:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "character_name": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Character name or identity tag.",
                    },
                ),
                "appearance": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Face, hair, age, and identifying visual traits.",
                    },
                ),
                "body": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Body proportions, physique, and anatomy descriptors.",
                    },
                ),
                "clothing": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Outfit, accessories, and materials.",
                    },
                ),
                "pose": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Body pose and camera-facing orientation.",
                    },
                ),
                "expression": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Facial expression and emotion.",
                    },
                ),
                "scene": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Environment, lighting, and composition context.",
                    },
                ),
                "style_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Style and rendering tags, comma-separated.",
                    },
                ),
                "quality_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Quality/detail tags, comma-separated.",
                    },
                ),
                "negative_tags": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
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

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "sections")
    FUNCTION = "build_prompt"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Builds positive/negative prompts from character sections with optional cleanup and dedupe."

    @staticmethod
    def _clean_value(text: str) -> str:
        value = (text or "").replace("\n", " ").strip(" ,")
        value = _MULTI_SPACE_RE.sub(" ", value)
        return value.strip()

    @staticmethod
    def _split_tokens(text: str) -> list[str]:
        raw = text.replace("\n", ",")
        return [part.strip() for part in _SPLIT_RE.split(raw) if part.strip()]

    @staticmethod
    def _dedupe_tokens(items: list[str]) -> list[str]:
        seen = set()
        output = []
        for item in items:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
        return output

    def _format_positive(self, values: list[str], format_mode: str) -> str:
        if not values:
            return ""
        if format_mode == "prose":
            if len(values) == 1:
                return values[0]
            return f"{', '.join(values[:-1])}, and {values[-1]}"
        if format_mode == "booru":
            return ", ".join(values)

        # Hybrid starts with the strongest identity tags, then the rest.
        if len(values) <= 3:
            return ", ".join(values)
        head = ", ".join(values[:3])
        tail = ", ".join(values[3:])
        return f"{head} | {tail}"

    def build_prompt(
        self,
        character_name,
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
        sections = {
            "character": character_name,
            "appearance": appearance,
            "body": body,
            "clothing": clothing,
            "pose": pose,
            "expression": expression,
            "scene": scene,
            "style": style_tags,
            "quality": quality_tags,
            "negative": negative_tags,
            "format_mode": format_mode,
        }
        return _build_prompts_from_sections(sections, cleanup=cleanup, dedupe=dedupe)


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
                        "tooltip": "Input positive prompt to clean.",
                    },
                ),
                "negative_prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
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
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("clean_positive", "clean_negative")
    FUNCTION = "clean_prompt"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Cleans positive and negative prompts by normalizing tags and optionally deduplicating."

    def _normalize(self, text: str, cleanup: bool, dedupe: bool) -> str:
        parts = BubbaCharacterPromptBuilder._split_tokens(text)
        if cleanup:
            parts = [BubbaCharacterPromptBuilder._clean_value(item) for item in parts]
            parts = [item for item in parts if item]
        if dedupe:
            parts = BubbaCharacterPromptBuilder._dedupe_tokens(parts)
        return ", ".join(parts)

    def clean_prompt(self, positive_prompt, negative_prompt, cleanup, dedupe):
        clean_positive = self._normalize(positive_prompt, cleanup, dedupe)
        clean_negative = self._normalize(negative_prompt, cleanup, dedupe)
        return (clean_positive, clean_negative)


class BubbaPromptPresetSave:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preset_name": (
                    "STRING",
                    {
                        "default": "CharacterPreset",
                        "multiline": False,
                        "tooltip": "Name used as the preset key in prompt_presets.json.",
                    },
                ),
                "sections": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Sections string from BubbaCharacterPromptBuilder.",
                    },
                ),
            },
            "optional": {
                "overwrite": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "When disabled, an existing preset name will not be replaced.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status", "saved_name")
    FUNCTION = "save_preset"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Saves Prompt Builder sections to prompt_presets.json in the node pack root folder."

    def save_preset(self, preset_name, sections, overwrite=True):
        safe_name = (preset_name or "").strip() or "CharacterPreset"
        parsed_sections = _parse_sections_text(sections)

        presets = _read_presets_file()
        if not overwrite and safe_name in presets:
            return (f"Preset '{safe_name}' already exists (overwrite disabled).", safe_name)

        presets[safe_name] = parsed_sections
        _write_presets_file(presets)
        return (f"Saved preset '{safe_name}' to {_presets_file_path().name}.", safe_name)


class BubbaPromptPreset:
    @classmethod
    def _preset_names(cls) -> list[str]:
        names = sorted(_read_presets_file().keys())
        return names if names else ["(no presets found)"]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preset_name": (
                    s._preset_names(),
                    {
                        "default": s._preset_names()[0],
                        "tooltip": "Preset to load from prompt_presets.json.",
                    },
                ),
                "character_name": ("STRING", {"default": "", "multiline": False, "tooltip": "Override character section when not empty."}),
                "appearance": ("STRING", {"default": "", "multiline": True, "tooltip": "Override appearance section when not empty."}),
                "body": ("STRING", {"default": "", "multiline": True, "tooltip": "Override body section when not empty."}),
                "clothing": ("STRING", {"default": "", "multiline": True, "tooltip": "Override clothing section when not empty."}),
                "pose": ("STRING", {"default": "", "multiline": True, "tooltip": "Override pose section when not empty."}),
                "expression": ("STRING", {"default": "", "multiline": True, "tooltip": "Override expression section when not empty."}),
                "scene": ("STRING", {"default": "", "multiline": True, "tooltip": "Override scene section when not empty."}),
                "style_tags": ("STRING", {"default": "", "multiline": True, "tooltip": "Override style section when not empty."}),
                "quality_tags": ("STRING", {"default": "", "multiline": True, "tooltip": "Override quality section when not empty."}),
                "negative_tags": ("STRING", {"default": "", "multiline": True, "tooltip": "Override negative section when not empty."}),
                "format_mode": (
                    ["booru", "prose", "hybrid"],
                    {
                        "default": "hybrid",
                        "tooltip": "Format mode used when override_format_mode is enabled.",
                    },
                ),
                "override_format_mode": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable to use the format_mode input instead of the preset value.",
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
                        "tooltip": "Remove duplicate tags while preserving order.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt", "sections", "loaded_name")
    FUNCTION = "build_from_preset"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Loads a saved JSON preset and lets you override sections by entering text in matching fields."

    def build_from_preset(
        self,
        preset_name,
        character_name,
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
        override_format_mode,
        cleanup,
        dedupe,
    ):
        presets = _read_presets_file()
        sections = _default_sections()
        if preset_name in presets:
            sections.update(presets[preset_name])

        overrides = {
            "character": character_name,
            "appearance": appearance,
            "body": body,
            "clothing": clothing,
            "pose": pose,
            "expression": expression,
            "scene": scene,
            "style": style_tags,
            "quality": quality_tags,
            "negative": negative_tags,
        }
        for key, value in overrides.items():
            if (value or "").strip():
                sections[key] = value

        if override_format_mode:
            sections["format_mode"] = format_mode

        positive_prompt, negative_prompt, sections_text = _build_prompts_from_sections(
            sections,
            cleanup=cleanup,
            dedupe=dedupe,
        )
        return (positive_prompt, negative_prompt, sections_text, preset_name)
