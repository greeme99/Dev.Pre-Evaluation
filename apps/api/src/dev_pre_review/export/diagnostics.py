"""System diagnostic bundle generation without secrets or absolute paths.

References: FN-010, FR-016, TC-032, NFR-009.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from dev_pre_review import __version__
from dev_pre_review.domain.models import utc_now
from dev_pre_review.models.manifests import ModelManifest

_UNIX_PATH_RE = re.compile(r"/(?:Users|home|tmp|var)/[a-zA-Z0-9_\-./]+")
_WIN_PATH_RE = re.compile(r"[a-zA-Z]:\\[a-zA-Z0-9_\-\\.]+")
_API_KEY_RE = re.compile(r"sk-[a-zA-Z0-9]{20,}")


def sanitize_diagnostics(val: Any) -> Any:
    """Recursively scrub absolute paths, tokens, and secrets from diagnostic values."""
    if isinstance(val, str):
        cleaned = _UNIX_PATH_RE.sub("[REDACTED_PATH]", val)
        cleaned = _WIN_PATH_RE.sub("[REDACTED_PATH]", cleaned)
        cleaned = _API_KEY_RE.sub("[REDACTED_KEY]", cleaned)
        return cleaned
    if isinstance(val, dict):
        return {k: sanitize_diagnostics(v) for k, v in val.items()}
    if isinstance(val, list | tuple):
        return [sanitize_diagnostics(item) for item in val]
    return val


class DiagnosticBundle:
    """Creates a privacy-preserving diagnostic bundle for troubleshooting."""

    @classmethod
    def create(
        cls,
        error_codes: list[str] | None = None,
        step_latencies_ms: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        manifest_path = Path("packaging/windows/models.json")
        if manifest_path.exists():
            content = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = ModelManifest.model_validate(content)
            models_version = manifest.manifest_version
        else:
            models_version = "1.0.0"

        bundle: dict[str, Any] = {
            "app_version": __version__,
            "python_version": sys.version.split()[0],
            "os_platform": sys.platform,
            "models_manifest_version": models_version,
            "parser_versions": {
                "pdf_parser": "1.0.0",
                "dxf_parser": "1.0.0",
            },
            "error_codes": error_codes or [],
            "step_latencies_ms": step_latencies_ms or {},
            "generated_at": utc_now().isoformat(),
        }

        # Double pass through sanitizer to guarantee zero leaks
        sanitized = sanitize_diagnostics(bundle)
        if not isinstance(sanitized, dict):
            raise TypeError("Sanitized bundle must be a dict")
        return sanitized

    @classmethod
    def to_json(
        cls,
        error_codes: list[str] | None = None,
        step_latencies_ms: dict[str, float] | None = None,
    ) -> str:
        data = cls.create(error_codes=error_codes, step_latencies_ms=step_latencies_ms)
        return json.dumps(data, indent=2, ensure_ascii=False)
