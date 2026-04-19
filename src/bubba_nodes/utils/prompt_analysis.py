from .prompting import clean_prompt_value, dedupe_prompt_tokens, split_prompt_tokens

# Keep this list concise and practical for prompt quality checks.
CONFLICT_PAIRS: tuple[tuple[str, str], ...] = (
    ("solo", "multiple people"),
    ("male", "female"),
    ("day", "night"),
    ("indoors", "outdoors"),
    ("safe", "nsfw"),
)


def find_duplicate_prompt_tokens(parts: list[str]) -> list[str]:
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


def find_pair_conflicts(parts: list[str]) -> list[str]:
    normalized = {part.strip().lower() for part in parts if part.strip()}
    warnings: list[str] = []
    for left, right in CONFLICT_PAIRS:
        if left in normalized and right in normalized:
            warnings.append(f"{left} <-> {right}")
    return warnings


def normalize_prompt_csv(text: str, cleanup: bool, dedupe: bool) -> str:
    parts = split_prompt_tokens(text)
    if cleanup:
        parts = [clean_prompt_value(item) for item in parts]
        parts = [item for item in parts if item]
    if dedupe:
        parts = dedupe_prompt_tokens(parts)
    return ", ".join(parts)
