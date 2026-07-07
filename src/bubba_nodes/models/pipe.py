from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .metadata import BubbaMetadata


@dataclass(frozen=True)
class BubbaPipe:
    """Generation context carried between Bubba pipe-aware nodes."""

    model: Any | None = None
    clip: Any | None = None
    vae: Any | None = None
    positive: Any | None = None
    negative: Any | None = None
    positive_prompt: str = ""
    negative_prompt: str = ""
    image: Any | None = None
    mask: Any | None = None
    latent: Any | None = None
    metadata: BubbaMetadata = field(default_factory=BubbaMetadata)

    @classmethod
    def empty(cls) -> "BubbaPipe":
        return cls()

    @classmethod
    def coerce(cls, value: Any) -> "BubbaPipe":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            data = dict(value)
            data["metadata"] = BubbaMetadata.coerce(data.get("metadata"))
            allowed = set(cls.__dataclass_fields__)
            return cls(**{key: item for key, item in data.items() if key in allowed})
        return cls()

    def updated(self, **changes: Any) -> "BubbaPipe":
        if "metadata" in changes:
            changes["metadata"] = BubbaMetadata.coerce(changes["metadata"])
        return replace(self, **changes)

    def with_metadata(self, **changes: Any) -> "BubbaPipe":
        return self.updated(metadata=self.metadata.updated(**changes))


def resolve_pipe_value(override: Any, pipe_value: Any, name: str):
    if override is not None:
        return override
    if pipe_value is not None:
        return pipe_value
    raise ValueError(f"Bubba pipe is missing required value: {name}. Connect a {name} input or provide it in the pipe.")
