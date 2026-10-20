"""Tests for diagnostic bundle creation without sensitive data (FN-010, FR-016, TC-032, NFR-009)."""

import json
import re

from dev_pre_review.export.diagnostics import DiagnosticBundle


def test_create_diagnostic_bundle_contains_versions_and_metrics() -> None:
    bundle_data = DiagnosticBundle.create(
        error_codes=["ERR_TEST_01", "ERR_TIMEOUT"],
        step_latencies_ms={"extract": 120.5, "retrieve": 45.2, "evaluate": 12.0},
    )

    assert "app_version" in bundle_data
    assert "os_platform" in bundle_data
    assert "error_codes" in bundle_data
    assert "step_latencies_ms" in bundle_data
    assert bundle_data["error_codes"] == ["ERR_TEST_01", "ERR_TIMEOUT"]


def test_diagnostic_bundle_never_contains_secrets_or_absolute_paths() -> None:
    bundle_data = DiagnosticBundle.create(
        error_codes=["ERR_FAILED_UPLOAD"],
        step_latencies_ms={"extract": 100},
    )
    serialized = json.dumps(bundle_data, ensure_ascii=False)

    # 1. No absolute paths (Windows C:\ or Unix /Users, /home, /tmp)
    unix_path_pattern = re.compile(r"/(?:Users|home|tmp|var)/[a-zA-Z0-9_\-./]+")
    windows_path_pattern = re.compile(r"[a-zA-Z]:\\[a-zA-Z0-9_\-\\.]+")

    assert not unix_path_pattern.search(serialized), f"Absolute Unix path found: {serialized}"
    assert not windows_path_pattern.search(serialized), f"Absolute Windows path found: {serialized}"

    # 2. No OpenAI or generic API keys
    api_key_pattern = re.compile(r"sk-[a-zA-Z0-9]{20,}")
    assert not api_key_pattern.search(serialized), f"API Key found: {serialized}"
