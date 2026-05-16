import re
from pathlib import PureWindowsPath


_INVALID_WINDOWS_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_path_component(value: str, fallback: str) -> str:
    """Return a Windows-safe path component without changing ordinary names."""
    text = str(value or "").strip().replace(" ", "_")
    text = _INVALID_WINDOWS_CHARS_RE.sub("", text)
    text = text.strip(" .")
    if not text:
        return fallback

    stem = text.split(".", 1)[0].upper()
    if stem in _RESERVED_WINDOWS_NAMES:
        text = f"_{text}"
    return text


def sanitize_relative_save_prefix(value: str, fallback: str = "Character/Scene") -> str:
    """Sanitize a relative folder/name prefix before passing it to ComfyUI saving.

    Bubba save prefixes are intentionally relative values such as
    ``Character/Scene``. Absolute paths, drive-qualified paths, UNC paths, and
    parent traversal are collapsed into safe relative components.
    """
    raw = str(value or "").replace("\\", "/").strip()
    if not raw:
        raw = fallback

    windows_path = PureWindowsPath(raw)
    if raw.startswith("/") or raw.startswith("//") or windows_path.drive or windows_path.root:
        raw = raw.replace(":", "/").lstrip("/")

    parts: list[str] = []
    for part in raw.split("/"):
        candidate = part.strip()
        if not candidate or candidate in {".", ".."}:
            continue
        parts.append(sanitize_path_component(candidate, "untitled"))

    if not parts:
        return fallback
    return "/".join(parts)
