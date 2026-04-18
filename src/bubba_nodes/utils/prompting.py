import re

# TODO(new-feature): Support weighted tags syntax helpers (e.g., (tag:1.2)) with optional normalization rules.
# TODO(optimize): Memoize prompt section normalization for repeated identical section payloads.


_SPLIT_RE = re.compile(r"\s*,\s*")
_MULTI_SPACE_RE = re.compile(r"\s+")

SECTION_KEYS: tuple[str, ...] = (
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
)

POSITIVE_SECTION_KEYS: tuple[str, ...] = (
    "character",
    "appearance",
    "body",
    "clothing",
    "pose",
    "expression",
    "scene",
    "style",
    "quality",
)


def default_prompt_sections() -> dict[str, str]:
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


def assemble_prompt_sections(
    appearance: str,
    body: str,
    clothing: str,
    pose: str,
    expression: str,
    scene: str,
    style_tags: str,
    quality_tags: str,
    negative_tags: str,
    format_mode: str,
    character: str = "",
) -> dict[str, str]:
    return {
        "character": character,
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


def clean_prompt_value(text: str) -> str:
    value = (text or "").replace("\n", " ").strip(" ,")
    value = _MULTI_SPACE_RE.sub(" ", value)
    return value.strip()


def split_prompt_tokens(text: str) -> list[str]:
    raw = (text or "").replace("\n", ",")
    return [part.strip() for part in _SPLIT_RE.split(raw) if part.strip()]


def dedupe_prompt_tokens(items: list[str]) -> list[str]:
    seen = set()
    output: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def format_positive_prompt(values: list[str], format_mode: str) -> str:
    if not values:
        return ""
    if format_mode == "prose":
        if len(values) == 1:
            return values[0]
        return f"{', '.join(values[:-1])}, and {values[-1]}"
    if format_mode == "booru":
        return ", ".join(values)

    if len(values) <= 3:
        return ", ".join(values)
    head = ", ".join(values[:3])
    tail = ", ".join(values[3:])
    return f"{head} | {tail}"


def build_prompts_from_sections(
    sections: dict[str, str],
    cleanup: bool,
    dedupe: bool,
    include_character_in_positive: bool = True,
) -> tuple[str, str, str]:
    # TODO(optimize): Reduce intermediate string joins by building token arrays once and formatting at the end.
    normalized = default_prompt_sections()
    normalized.update(sections)

    format_mode = normalized.get("format_mode", "hybrid")
    if format_mode not in ("booru", "prose", "hybrid"):
        format_mode = "hybrid"
        normalized["format_mode"] = format_mode

    positive_tokens: list[str] = []
    section_lines: list[str] = []

    for key in POSITIVE_SECTION_KEYS:
        value = (normalized.get(key, "") or "").strip()
        if cleanup:
            value = clean_prompt_value(value)
        normalized[key] = value
        if value:
            parts = split_prompt_tokens(value)
            if dedupe:
                parts = dedupe_prompt_tokens(parts)
            value = ", ".join(parts)
            normalized[key] = value
            if include_character_in_positive or key != "character":
                positive_tokens.extend(parts)
        section_lines.append(f"{key}: {normalized[key]}")

    negative_value = (normalized.get("negative", "") or "").strip()
    if cleanup:
        negative_value = clean_prompt_value(negative_value)
    negative_parts = split_prompt_tokens(negative_value)
    if cleanup:
        cleaned_negative_parts = []
        for item in negative_parts:
            cleaned = clean_prompt_value(item)
            if cleaned:
                cleaned_negative_parts.append(cleaned)
        negative_parts = cleaned_negative_parts
    if dedupe:
        negative_parts = dedupe_prompt_tokens(negative_parts)
    normalized["negative"] = ", ".join(negative_parts)

    if dedupe:
        positive_tokens = dedupe_prompt_tokens(positive_tokens)

    positive_prompt = format_positive_prompt(positive_tokens, format_mode)

    section_lines.append(f"negative: {normalized['negative']}")
    section_lines.append(f"format_mode: {normalized['format_mode']}")
    sections_text = "\n".join(section_lines)

    return (positive_prompt, normalized["negative"], sections_text)


def encode_conditioning(clip, text: str):
    tokens = clip.tokenize(text or "")
    if hasattr(clip, "encode_from_tokens_scheduled"):
        return clip.encode_from_tokens_scheduled(tokens)

    cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
    return [[cond, {"pooled_output": pooled}]]


def empty_conditioning():
    return [[None, {}]]
