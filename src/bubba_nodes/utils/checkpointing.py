import hashlib
from functools import lru_cache
from pathlib import Path


def checkpoint_display_name(ckpt_name: str) -> str:
    raw = str(ckpt_name or "").strip()
    if not raw:
        return ""

    leaf = raw.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in leaf:
        leaf = leaf.rsplit(".", 1)[0]
    return leaf


@lru_cache(maxsize=128)
def _cached_sha256(path_text: str, size: int, mtime_ns: int) -> str:
    digest = hashlib.sha256()
    with open(path_text, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint_sha256(path: str | Path) -> str:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return _cached_sha256(str(resolved), stat.st_size, stat.st_mtime_ns)


def checkpoint_short_hash(path: str | Path, length: int = 10) -> str:
    return checkpoint_sha256(path)[:length]
