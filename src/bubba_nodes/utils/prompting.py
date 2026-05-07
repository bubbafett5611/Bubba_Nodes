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


def normalize_prompt_section_value(text: str, cleanup: bool) -> str:
    value = str(text or "").strip()
    if cleanup:
        return clean_prompt_value(value)
    return value


def prompt_value_to_tokens(text: str, cleanup: bool, dedupe: bool) -> list[str]:
    value = normalize_prompt_section_value(text, cleanup)
    tokens = split_prompt_tokens(value)
    if cleanup:
        tokens = [clean_prompt_value(item) for item in tokens]
        tokens = [item for item in tokens if item]
    if dedupe:
        tokens = dedupe_prompt_tokens(tokens)
    return tokens


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
        section_value = normalize_prompt_section_value(normalized.get(key, ""), cleanup)
        normalized[key] = section_value
        if section_value:
            section_tokens = prompt_value_to_tokens(section_value, cleanup, dedupe)
            normalized[key] = ", ".join(section_tokens)
            if include_character_in_positive or key != "character":
                positive_tokens.extend(section_tokens)
        section_lines.append(f"{key}: {normalized[key]}")

    negative_tokens = prompt_value_to_tokens(normalized.get("negative", ""), cleanup, dedupe)
    normalized["negative"] = ", ".join(negative_tokens)

    if dedupe:
        positive_tokens = dedupe_prompt_tokens(positive_tokens)

    positive_prompt = format_positive_prompt(positive_tokens, format_mode)

    section_lines.append(f"negative: {normalized['negative']}")
    section_lines.append(f"format_mode: {normalized['format_mode']}")
    sections_text = "\n".join(section_lines)

    return (positive_prompt, normalized["negative"], sections_text)


def encode_conditioning(clip, text: str):
    if clip is None:
        print(
            "[Bubba] WARNING: CLIP is None — the loaded model may not include a CLIP encoder "
            "(e.g. unet-only or distilled model). Returning empty conditioning."
        )
        return empty_conditioning()

    def _encode_with_tokens(raw_text: str):
        tokens = clip.tokenize(raw_text)
        if hasattr(clip, "encode_from_tokens_scheduled"):
            return clip.encode_from_tokens_scheduled(tokens)
        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        return [[cond, {"pooled_output": pooled}]]

    # Some text encoders (notably Anima/Qwen integrations) can throw a token
    # conversion TypeError for weighted prompt syntax. Retry once with a
    # de-weighted/plain-text variant before falling back to empty conditioning.
    source_text = text or ""
    try:
        return _encode_with_tokens(source_text)
    except TypeError as exc:
        simplified = re.sub(r"\(([^()]+?):\s*[-+]?\d*\.?\d+\)", r"\1", source_text)
        simplified = simplified.replace("(", "").replace(")", "")
        simplified = simplified.replace("[", "").replace("]", "")
        simplified = _MULTI_SPACE_RE.sub(" ", simplified).strip()
        if simplified and simplified != source_text:
            try:
                print("[Bubba] WARNING: CLIP encoding failed with weighted prompt syntax; " "retrying with simplified prompt text.")
                return _encode_with_tokens(simplified)
            except TypeError as retry_exc:
                print("[Bubba] WARNING: CLIP encoding failed after simplified retry; " f"returning empty conditioning. Error: {retry_exc}")
                return empty_conditioning()

        print("[Bubba] WARNING: CLIP encoding failed; returning empty conditioning. " f"Error: {exc}")
        return empty_conditioning()


def empty_conditioning():
    return [[None, {}]]
