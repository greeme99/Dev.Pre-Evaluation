"""Model manifest specification and registry recommendation (FN-008, MOD-002~MOD-005)."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.models.hardware import HardwareProfile


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: str
    runtime: str
    url: str
    revision: str
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(gt=0)
    license: str
    min_ram_mb: int = 512
    min_vram_mb: int = 0
    optional: bool = False
    dimension: int | None = None


class ModelManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str
    models: dict[str, ModelInfo]


class ModelRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_provider: str
    rule_only_mode: bool
    missing_required_models: list[str]
    available_models: list[str]


class ModelRegistry:
    def __init__(self, models: dict[str, ModelInfo]) -> None:
        self.models = models

    @classmethod
    def load_from_path(cls, path: Path) -> "ModelRegistry":
        content = json.loads(path.read_text(encoding="utf-8"))
        manifest = ModelManifest.model_validate(content)
        return cls(models=manifest.models)

    def recommend(
        self,
        profile: HardwareProfile,
        cache_dir: Path | None = None,
    ) -> ModelRecommendation:
        missing_required: list[str] = []
        available: list[str] = []

        for key, model in self.models.items():
            is_present = False
            if cache_dir is not None and cache_dir.exists():
                model_file = cache_dir / f"{key}.bin"
                if model_file.exists():
                    is_present = True

            if is_present:
                available.append(key)
            elif not model.optional:
                missing_required.append(key)

        rule_only = len(missing_required) > 0

        return ModelRecommendation(
            execution_provider=profile.execution_provider,
            rule_only_mode=rule_only,
            missing_required_models=missing_required,
            available_models=available,
        )
