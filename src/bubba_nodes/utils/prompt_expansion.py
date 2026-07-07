from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_WILDCARD_DIR = Path(__file__).resolve().parents[1] / "data" / "wildcards"
DEFAULT_MAX_EXPANSION_DEPTH = 10
DEFAULT_MAX_PROMPT_LENGTH = 100_000

_CHOICE_RE = re.compile(r"(?<!\\)\{([^{}]*?(?<!\\)\|[^{}]*?)\}")
_WILDCARD_RE = re.compile(r"(?<!\\)__([A-Za-z0-9][A-Za-z0-9_./-]*)__")
_UNESCAPE_RE = re.compile(r"\\([\\{}_$|])")


@dataclass(frozen=True)
class PromptSelection:
    kind: str
    source: str
    value: str


@dataclass(frozen=True)
class PromptExpansionResult:
    raw_text: str
    resolved_text: str
    seed: int
    selections: tuple[PromptSelection, ...] = ()
    warnings: tuple[str, ...] = ()

    def format_report(self, label: str = "Prompt") -> str:
        lines = [
            f"{label} raw: {self.raw_text}",
            f"{label} resolved: {self.resolved_text}",
            f"{label} expansion seed: {self.seed}",
        ]
        if self.selections:
            lines.append(f"{label} selections:")
            lines.extend(f"- {selection.kind} {selection.source!r} -> {selection.value!r}" for selection in self.selections)
        if self.warnings:
            lines.append(f"{label} warnings:")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


def _stable_index(seed: int, field_name: str, kind: str, source: str, occurrence: int, item_count: int) -> int:
    payload = f"{int(seed)}\0{field_name}\0{kind}\0{source}\0{occurrence}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") % item_count


def _split_unescaped_choices(value: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", value)
    return [part.replace(r"\|", "|").strip() for part in parts]


def _normalize_wildcard_roots(wildcard_roots: Iterable[Path | str] | None) -> tuple[Path, ...]:
    roots = tuple(Path(root).resolve() for root in (wildcard_roots or (DEFAULT_WILDCARD_DIR,)))
    return tuple(root for root in roots if root.is_dir())


def _resolve_wildcard_path(name: str, roots: tuple[Path, ...]) -> Path | None:
    relative = Path(name.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if relative.suffix.lower() != ".txt":
        relative = relative.with_suffix(".txt")

    for root in roots:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _load_wildcard_items(path: Path) -> list[str]:
    items: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            items.append(value)
    return items


def expand_prompt_text(
    text: str,
    *,
    seed: int = 0,
    field_name: str = "prompt",
    wildcard_roots: Iterable[Path | str] | None = None,
    max_depth: int = DEFAULT_MAX_EXPANSION_DEPTH,
    max_length: int = DEFAULT_MAX_PROMPT_LENGTH,
) -> PromptExpansionResult:
    raw_text = str(text or "")
    resolved = raw_text
    roots = _normalize_wildcard_roots(wildcard_roots)
    selections: list[PromptSelection] = []
    warnings: list[str] = []
    counters = {"choice": 0, "wildcard": 0}
    seen_values = {resolved}

    def replace_choice(match: re.Match[str]) -> str:
        source = match.group(0)
        options = _split_unescaped_choices(match.group(1))
        if len(options) < 2:
            return source
        occurrence = counters["choice"]
        counters["choice"] += 1
        selected = options[_stable_index(seed, field_name, "choice", source, occurrence, len(options))]
        selections.append(PromptSelection(kind="choice", source=source, value=selected))
        return selected

    def replace_wildcard(match: re.Match[str]) -> str:
        source = match.group(0)
        name = match.group(1)
        occurrence = counters["wildcard"]
        counters["wildcard"] += 1
        path = _resolve_wildcard_path(name, roots)
        if path is None:
            warnings.append(f"Wildcard {source} was not found.")
            return source
        try:
            items = _load_wildcard_items(path)
        except (OSError, UnicodeError) as error:
            warnings.append(f"Wildcard {source} could not be read: {error}")
            return source
        if not items:
            warnings.append(f"Wildcard {source} has no selectable lines.")
            return source
        selected = items[_stable_index(seed, field_name, "wildcard", name, occurrence, len(items))]
        selections.append(PromptSelection(kind="wildcard", source=name, value=selected))
        return selected

    depth = max(1, int(max_depth))
    for _ in range(depth):
        expanded = _WILDCARD_RE.sub(replace_wildcard, resolved)
        expanded = _CHOICE_RE.sub(replace_choice, expanded)
        if len(expanded) > max_length:
            warnings.append(f"Resolved prompt exceeded the {max_length}-character limit and was truncated.")
            resolved = expanded[:max_length]
            break
        if expanded == resolved:
            break
        if expanded in seen_values:
            warnings.append("Prompt expansion stopped after detecting a recursive cycle.")
            resolved = expanded
            break
        seen_values.add(expanded)
        resolved = expanded
    else:
        if _WILDCARD_RE.search(resolved) or _CHOICE_RE.search(resolved):
            warnings.append(f"Prompt expansion stopped at the maximum depth of {depth}.")

    resolved = _UNESCAPE_RE.sub(r"\1", resolved)
    return PromptExpansionResult(
        raw_text=raw_text,
        resolved_text=resolved,
        seed=int(seed),
        selections=tuple(selections),
        warnings=tuple(dict.fromkeys(warnings)),
    )
