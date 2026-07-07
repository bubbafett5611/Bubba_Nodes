from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from comfy_api.latest import IO

from ..models import BubbaMetadata, BubbaPipe
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


class BubbaPromptRandomizer(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        auto = lambda group: {"bubba.autocomplete": {"group": group}}
        inputs = [
            IO.Int.Input("seed", default=0, min=0, max=2**32 - 1),
            IO.String.Input("prefix_text", default="", multiline=True, extra_dict=auto("quality")),
            IO.String.Input("extra_positive", default="", multiline=True, extra_dict=auto("positive")),
            IO.String.Input("negative_prompt", default="", multiline=True, extra_dict=auto("negative")),
            IO.Boolean.Input("cleanup", default=True),
            IO.Boolean.Input("dedupe", default=True),
            IO.Boolean.Input("remove_category_underscores", default=False),
        ]
        for category_name, items in load_prompt_randomizer_categories().items():
            inputs.append(IO.Combo.Input(category_name, options=[_DISABLED, _RANDOM, *items], default=_DISABLED))
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        inputs += [pipe.Input("pipe", optional=True), metadata.Input("metadata", optional=True), IO.Clip.Input("clip", optional=True)]
        return IO.Schema(
            node_id="BubbaPromptRandomizer",
            display_name="Bubba Prompt Randomizer",
            category="Bubba Nodes/Prompt",
            description="Builds a prompt from JSON-backed category choices and freeform text.",
            inputs=inputs,
            outputs=[
                pipe.Output("pipe"),
                metadata.Output("metadata"),
                IO.Conditioning.Output("positive"),
                IO.Conditioning.Output("negative"),
                IO.String.Output("positive_prompt"),
                IO.String.Output("negative_prompt"),
                IO.String.Output("chosen_values"),
            ],
        )

    @classmethod
    def execute(cls, **kwargs):
        seed = int(kwargs.get("seed", 0) or 0)
        cleanup = bool(kwargs.get("cleanup", True))
        dedupe = bool(kwargs.get("dedupe", True))
        remove_category_underscores = bool(kwargs.get("remove_category_underscores", False))
        source_pipe = BubbaPipe.coerce(kwargs.get("pipe"))
        clip = kwargs.get("clip") if kwargs.get("clip") is not None else source_pipe.clip
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

        positive_prompt = cls._normalize_prompt_parts(
            [
                kwargs.get("prefix_text", ""),
                *selected_parts,
                kwargs.get("extra_positive", ""),
            ],
            cleanup=cleanup,
            dedupe=dedupe,
        )
        negative_prompt = cls._normalize_prompt_parts(
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

        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata).updated(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )
        updated_pipe = source_pipe.updated(
            clip=clip,
            positive=positive_conditioning,
            negative=negative_conditioning,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            metadata=updated_metadata,
        )
        chosen_values = "\n".join(chosen_lines) if chosen_lines else "none"

        return IO.NodeOutput(
            updated_pipe,
            updated_metadata,
            positive_conditioning,
            negative_conditioning,
            positive_prompt,
            negative_prompt,
            chosen_values,
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
