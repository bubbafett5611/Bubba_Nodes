import json
from typing import Any, Mapping

from pydantic import BaseModel, Field, field_validator

# TODO(new-feature): Introduce metadata schema_version with migration helpers for backward-compatible evolution.
# TODO(optimize): Consider a lightweight validation cache for repeated coercions of identical metadata payloads.


class BubbaMetadata(BaseModel):
    """Metadata container for generation info, prompts, and workflow state."""

    # Generation info - populated by sampler
    model_name: str = Field(default="", description="Model/checkpoint name used for generation")
    clip_skip: int = Field(default=0, ge=0, description="Number of CLIP layers to skip during encoding")
    sampler_time_seconds: float = Field(default=0.0, ge=0.0, description="Time taken for sampling in seconds")
    steps: int = Field(default=0, ge=0, description="Number of sampling steps")
    cfg: float = Field(default=0.0, ge=0.0, description="Classifier-free guidance scale")
    sampler_name: str = Field(default="", description="Name of the sampler algorithm")
    scheduler: str = Field(default="", description="Noise scheduler used")
    denoise: float = Field(default=0.0, ge=0.0, le=1.0, description="Denoising strength (0-1)")
    seed: int = Field(default=0, ge=0, description="Random seed for generation")

    # Prompt info - populated by prompt builders
    positive_prompt: str = Field(default="", description="Positive prompt used for generation")
    negative_prompt: str = Field(default="", description="Negative prompt used for generation")

    # LoRA info - appended by each BubbaLoraLoader in the chain
    loras: list[str] = Field(default_factory=list, description="LoRA names applied during generation, in order")

    # Workflow info
    filepath: str = Field(default="", description="Output filepath or path prefix")

    model_config = {
        "str_strip_whitespace": True,
        "json_schema_extra": {
            "examples": [
                {
                    "model_name": "model.safetensors",
                    "seed": 42,
                    "steps": 20,
                    "cfg": 7.5,
                    "sampler_name": "euler",
                    "scheduler": "karras",
                }
            ]
        },
    }

    @field_validator("steps", "seed", "clip_skip", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        try:
            parsed = int(v)
            return parsed if parsed >= 0 else 0
        except (ValueError, TypeError):
            return 0

    @field_validator("cfg", "sampler_time_seconds", "denoise", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> float:
        try:
            parsed = float(v)
            return max(0.0, parsed)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("loras", mode="before")
    @classmethod
    def coerce_loras(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(item).strip() for item in v if item]
        if isinstance(v, str):
            # Handle comma-separated string fallback
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

    @field_validator("model_name", "sampler_name", "scheduler", "positive_prompt", "negative_prompt", "filepath", mode="before")
    @classmethod
    def coerce_text(cls, v: Any) -> str:
        return str(v or "").strip()

    def formatted_sampler_info(self) -> str:
        """Generate formatted sampler info string from individual fields."""
        if self.steps <= 0 and not self.sampler_name and not self.scheduler and self.denoise <= 0.0 and self.seed <= 0:
            return ""

        info = (
            f"Time: {self.sampler_time_seconds:.3f}s  Seed: {self.seed}  Steps: {self.steps}  CFG: {self.cfg}"
            f"  Sampler: {self.sampler_name}  Scheduler: {self.scheduler}  Denoise: {self.denoise}"
        )
        if self.loras:
            info += f"  LoRAs: {', '.join(self.loras)}"
        return info

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BubbaMetadata":
        """Create BubbaMetadata from a mapping/dict, validating and normalizing fields."""
        return cls(**payload)

    @classmethod
    def from_json(cls, metadata_json: str) -> "BubbaMetadata":
        """Create BubbaMetadata from JSON string."""
        try:
            payload = json.loads(metadata_json or "{}")
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        return cls.from_mapping(payload)

    @classmethod
    def coerce(cls, value: Any) -> "BubbaMetadata":
        """Coerce various types into BubbaMetadata."""
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.from_mapping(value)
        if isinstance(value, str):
            return cls.from_json(value)
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return self.model_dump()

    def to_json(self, pretty: bool = False) -> str:
        """Convert to JSON string for serialization."""
        data = self.to_dict()
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)

    def updated(self, **changes: Any) -> "BubbaMetadata":
        """Return a new BubbaMetadata with specified fields updated."""
        data = self.model_dump()
        data.update(changes)
        return BubbaMetadata.from_mapping(data)
