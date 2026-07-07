from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BubbaCheckpointMerge:
    """In-memory checkpoint merge payload passed to Bubba Save Checkpoint."""

    state_dict: dict[str, Any]
    recipe: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    suggested_name: str = ""

    @classmethod
    def coerce(cls, value: Any) -> "BubbaCheckpointMerge":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict) and isinstance(value.get("state_dict"), dict):
            return cls(
                state_dict=value["state_dict"],
                recipe=dict(value.get("recipe") or {}),
                metadata={str(k): str(v) for k, v in dict(value.get("metadata") or {}).items()},
                suggested_name=str(value.get("suggested_name") or ""),
            )
        raise ValueError("Expected a Bubba checkpoint merge payload.")
