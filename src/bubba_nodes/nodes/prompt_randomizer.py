from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from ..models import BubbaMetadata
from ..utils.prompting import (
    clean_prompt_value,
    dedupe_prompt_tokens,
    empty_conditioning,
    encode_conditioning,
    split_prompt_tokens,
)


logger = logging.getLogger("bubba_nodes")

_CATEGORY_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")
_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "prompt_randomizer"
_DISABLED = "disabled"
_RANDOM = "random"


def _category_name_from_path(path: Path) -> str:
    name = _CATEGORY_NAME_RE.sub("_", path.stem.strip().lower()).strip("_")
    return name


def _coerce_category_items(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []

    seen: set[str] = set()
    items: list[str] = []
    for item in payload:
        value = clean_prompt_value(str(item))
        if not value:
            continue
        key = value.lower()
        if key in seen or key in {_DISABLED, _RANDOM}:
            continue
        seen.add(key)
        items.append(value)
    return items


def load_prompt_randomizer_categories(data_dir: Path | None = None) -> dict[str, list[str]]:
    data_dir = data_dir or _DATA_DIR
    categories: dict[str, list[str]] = {}
    if not data_dir.exists():
        return categories

    for path in sorted(data_dir.glob("*.json"), key=lambda item: item.name.lower()):
        category_name = _category_name_from_path(path)
        if not category_name:
            logger.warning("Skipping prompt randomizer category with invalid filename: %s", path)
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            logger.warning("Skipping prompt randomizer category %s: %s", path.name, error)
            continue

        items = _coerce_category_items(payload)
        if not items:
            logger.warning("Skipping empty prompt randomizer category: %s", path.name)
            continue
        categories[category_name] = items

    return categories


class BubbaPromptRandomizer:
    @classmethod
    def INPUT_TYPES(cls):
        required: dict[str, tuple[Any, dict[str, Any]]] = {
            "seed": (
                "INT",
                {
                    "default": 0,
                    "min": 0,
                    "max": 2**32 - 1,
                    "step": 1,
                    "tooltip": "Seed used for deterministic random category choices.",
                },
            ),
            "prefix_text": (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "bubba.autocomplete": {"group": "quality"},
                    "tooltip": "Stable positive prompt text placed before randomized category choices.",
                },
            ),
            "extra_positive": (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "bubba.autocomplete": {"group": "positive"},
                    "tooltip": "Additional positive prompt text placed after randomized category choices.",
                },
            ),
            "negative_prompt": (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "bubba.autocomplete": {"group": "negative"},
                    "tooltip": "Negative prompt text to pass through with cleanup and dedupe options.",
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
                    "tooltip": "Remove duplicate prompt tokens while preserving first occurrence order.",
                },
            ),
            "remove_category_underscores": (
                "BOOLEAN",
                {
                    "default": False,
                    "tooltip": "Replace underscores with spaces only in selected category values.",
                },
            ),
        }

        for category_name, items in load_prompt_randomizer_categories().items():
            required[category_name] = (
                [_DISABLED, _RANDOM, *items],
                {
                    "default": _DISABLED,
                    "tooltip": f"Choose a {category_name.replace('_', ' ')} value, randomize it, or disable this category.",
                },
            )

        return {
            "required": required,
            "optional": {
                "clip": (
                    "CLIP",
                    {
                        "tooltip": "Optional CLIP to encode positive and negative conditioning outputs.",
                    },
                ),
                "metadata": (
                    "BUBBA_METADATA",
                    {
                        "tooltip": "Optional metadata object to update with randomized prompts.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "CONDITIONING", "CONDITIONING", "STRING", "BUBBA_METADATA")
    RETURN_NAMES = (
        "positive_prompt",
        "negative_prompt",
        "positive_conditioning",
        "negative_conditioning",
        "chosen_values",
        "metadata",
    )
    FUNCTION = "randomize_prompt"
    CATEGORY = "Bubba Nodes/Prompt"
    DESCRIPTION = "Builds a prompt from JSON-backed category dropdowns plus freeform positive and negative text."

    def randomize_prompt(self, **kwargs):
        seed = int(kwargs.get("seed", 0) or 0)
        cleanup = bool(kwargs.get("cleanup", True))
        dedupe = bool(kwargs.get("dedupe", True))
        remove_category_underscores = bool(kwargs.get("remove_category_underscores", False))
        clip = kwargs.get("clip")
        metadata = kwargs.get("metadata")

        categories = load_prompt_randomizer_categories()
        rng = random.Random(seed)

        selected_parts: list[str] = []
        chosen_lines: list[str] = []
        for category_name, items in categories.items():
            selection = str(kwargs.get(category_name, _DISABLED) or _DISABLED)
            if selection.lower() == _DISABLED:
                continue
            if selection.lower() == _RANDOM:
                selection = rng.choice(items)

            if remove_category_underscores:
                selection = selection.replace("_", " ")
            value = clean_prompt_value(selection) if cleanup else selection.strip()
            if not value:
                continue
            selected_parts.append(value)
            chosen_lines.append(f"{category_name}: {value}")

        positive_prompt = self._normalize_prompt_parts(
            [
                kwargs.get("prefix_text", ""),
                *selected_parts,
                kwargs.get("extra_positive", ""),
            ],
            cleanup=cleanup,
            dedupe=dedupe,
        )
        negative_prompt = self._normalize_prompt_parts(
            [kwargs.get("negative_prompt", "")],
            cleanup=cleanup,
            dedupe=dedupe,
        )

        if clip is None:
            positive_conditioning = empty_conditioning()
            negative_conditioning = empty_conditioning()
        else:
            positive_conditioning = encode_conditioning(clip, positive_prompt)
            negative_conditioning = encode_conditioning(clip, negative_prompt)

        updated_metadata = BubbaMetadata.coerce(metadata).updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
        chosen_values = "\n".join(chosen_lines) if chosen_lines else "none"

        return (
            positive_prompt,
            negative_prompt,
            positive_conditioning,
            negative_conditioning,
            chosen_values,
            updated_metadata,
        )

    @staticmethod
    def _normalize_prompt_parts(parts: list[Any], cleanup: bool, dedupe: bool) -> str:
        tokens: list[str] = []
        for part in parts:
            text = str(part or "")
            if cleanup:
                text = clean_prompt_value(text)
            tokens.extend(split_prompt_tokens(text))

        if cleanup:
            tokens = [clean_prompt_value(token) for token in tokens]
            tokens = [token for token in tokens if token]
        else:
            tokens = [token.strip() for token in tokens if token.strip()]

        if dedupe:
            tokens = dedupe_prompt_tokens(tokens)
        return ", ".join(tokens)
