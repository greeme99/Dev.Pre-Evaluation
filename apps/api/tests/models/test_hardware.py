"""Tests for hardware profiling, CUDA detection, and model manifest validation.
FN-008, MOD-001~MOD-005, TC-019, TC-020.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from dev_pre_review.models.hardware import HardwareDetector, HardwareProfile
from dev_pre_review.models.manifests import ModelInfo, ModelRegistry


def test_hardware_detector_falls_back_to_cpu_when_no_gpu() -> None:
    detector = HardwareDetector()

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch.dict("sys.modules", {"torch": mock_torch}), patch("shutil.which", return_value=None):
        profile = detector.detect()
        assert profile.has_cuda is False
        assert profile.execution_provider == "cpu"
        assert profile.ram_mb > 0
        assert profile.vram_mb == 0


def test_hardware_detector_detects_cuda_gpu() -> None:
    detector = HardwareDetector()

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_props = MagicMock()
    mock_props.total_memory = 8 * 1024 * 1024 * 1024
    mock_props.name = "NVIDIA RTX 4090"
    mock_torch.cuda.get_device_properties.return_value = mock_props

    with patch.dict("sys.modules", {"torch": mock_torch}):
        profile = detector.detect()
        assert profile.has_cuda is True
        assert profile.execution_provider == "cuda"
        assert profile.vram_mb == 8192
        assert profile.device_name == "NVIDIA RTX 4090"


def test_model_registry_validates_models_json_manifest(tmp_path: Path) -> None:
    manifest_path = Path("packaging/windows/models.json")
    assert manifest_path.exists(), "models.json must exist in packaging/windows"

    registry = ModelRegistry.load_from_path(manifest_path)
    assert len(registry.models) >= 4

    # Check required models
    assert "ocr" in registry.models
    assert "text_embedding" in registry.models
    assert "visual_embedding" in registry.models
    assert "generation" in registry.models

    # Verify sha256 format and size
    for _key, model in registry.models.items():
        assert len(model.sha256) == 64
        assert model.size_bytes > 0
        assert model.license in ("MIT", "Apache-2.0", "BSD-3-Clause")


def test_model_registry_recommends_rule_only_mode_when_models_missing() -> None:
    manifest_path = Path("packaging/windows/models.json")
    registry = ModelRegistry.load_from_path(manifest_path)

    profile = HardwareProfile(
        has_cuda=False,
        execution_provider="cpu",
        ram_mb=8192,
        vram_mb=0,
    )

    # Empty model cache directory -> models are missing
    recommendation = registry.recommend(profile, cache_dir=Path("/non_existent_cache_dir"))
    assert recommendation.rule_only_mode is True
    assert recommendation.missing_required_models == ["ocr", "text_embedding", "visual_embedding"]


def test_model_registry_requires_matching_size_and_hash(tmp_path: Path) -> None:
    content = b"verified local model"
    model = ModelInfo(
        name="test",
        type="ocr",
        runtime="onnx",
        url="https://example.invalid/model",
        revision="test",
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        license="MIT",
    )
    registry = ModelRegistry(models={"ocr": model})
    profile = HardwareProfile(has_cuda=False, execution_provider="cpu", ram_mb=8192, vram_mb=0)

    (tmp_path / "ocr.bin").write_bytes(content)
    valid = registry.recommend(profile, cache_dir=tmp_path)
    assert valid.available_models == ["ocr"]
    assert valid.rule_only_mode is False

    (tmp_path / "ocr.bin").write_bytes(b"tampered local model")
    invalid = registry.recommend(profile, cache_dir=tmp_path)
    assert invalid.available_models == []
    assert invalid.missing_required_models == ["ocr"]
    assert invalid.rule_only_mode is True


def test_model_manifest_rejects_non_hex_sha256(tmp_path: Path) -> None:
    manifest = {
        "manifest_version": "test",
        "models": {
            "ocr": {
                "name": "invalid",
                "type": "ocr",
                "runtime": "onnx",
                "url": "https://example.invalid/model",
                "revision": "test",
                "sha256": "z" * 64,
                "size_bytes": 1,
                "license": "MIT",
            }
        },
    }
    path = tmp_path / "invalid-models.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError):
        ModelRegistry.load_from_path(path)
