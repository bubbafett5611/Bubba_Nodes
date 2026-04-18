from dataclasses import dataclass
import json
from typing import Any, Mapping

# TODO(new-feature): Introduce metadata schema_version with migration helpers for backward-compatible evolution.
# TODO(optimize): Consider a lightweight validation cache for repeated coercions of identical metadata payloads.


@dataclass(slots=True)
class BubbaMetadata:
    model_name: str = ""
    sampler_info: str = ""
    positive_prompt: str = ""
    negative_prompt: str = ""
    seed: int = 0
    filepath: str = ""
    prompt_sections: str = ""

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_seed(value: Any) -> int:
        try:
            parsed = int(value)
            return parsed if parsed >= 0 else 0
        except Exception:
            return 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BubbaMetadata":
        return cls(
            model_name=cls._normalize_text(payload.get("model_name", "")),
            sampler_info=cls._normalize_text(payload.get("sampler_info", "")),
            positive_prompt=cls._normalize_text(payload.get("positive_prompt", "")),
            negative_prompt=cls._normalize_text(payload.get("negative_prompt", "")),
            seed=cls._normalize_seed(payload.get("seed", 0)),
            filepath=cls._normalize_text(payload.get("filepath", "")),
            prompt_sections=cls._normalize_text(payload.get("prompt_sections", "")),
        )

    @classmethod
    def from_json(cls, metadata_json: str) -> "BubbaMetadata":
        try:
            payload = json.loads(metadata_json or "{}")
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        return cls.from_mapping(payload)

    @classmethod
    def coerce(cls, value: Any) -> "BubbaMetadata":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.from_mapping(value)
        if isinstance(value, str):
            return cls.from_json(value)
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self._normalize_text(self.model_name),
            "sampler_info": self._normalize_text(self.sampler_info),
            "positive_prompt": self._normalize_text(self.positive_prompt),
            "negative_prompt": self._normalize_text(self.negative_prompt),
            "seed": self._normalize_seed(self.seed),
            "prompt_sections": self._normalize_text(self.prompt_sections),
            "filepath": self._normalize_text(self.filepath),
        }

    def to_json(self, pretty: bool = False) -> str:
        if pretty:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def updated(self, **changes: Any) -> "BubbaMetadata":
        payload = self.to_dict()
        payload.update(changes)
        return BubbaMetadata.from_mapping(payload)
