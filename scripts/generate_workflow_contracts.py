"""Generate the TypeScript contract for the project-to-findings API workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from dev_pre_review.main import create_app  # noqa: E402

SCHEMA_NAMES = (
    "CreateProjectRequest",
    "ProjectResponse",
    "DrawingUploadResponse",
    "CreateAnalysisRequest",
    "AnalysisJobResponse",
    "FindingsResponse",
    "Finding",
    "Evidence",
    "ImprovementSuggestion",
    "DrawingType",
    "JobState",
    "AnalysisStep",
    "FindingStatus",
    "Severity",
    "EvidenceKind",
)


def schema_type(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]

    if "enum" in schema:
        return " | ".join(f'"{value}"' for value in schema["enum"])

    if "prefixItems" in schema:
        return f"[{', '.join(schema_type(item) for item in schema['prefixItems'])}]"

    union = schema.get("anyOf") or schema.get("oneOf")
    if union:
        return " | ".join(schema_type(option) for option in union)

    kind = schema.get("type")
    if kind == "array":
        item = schema_type(schema.get("items", {}))
        return f"Array<{item}>"
    if kind == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"Record<string, {schema_type(additional)}>"
        if additional is True:
            return "Record<string, unknown>"
        return "Record<string, unknown>"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    return "string"


def render(openapi: dict[str, Any]) -> str:
    schemas = openapi["components"]["schemas"]
    missing = [name for name in SCHEMA_NAMES if name not in schemas]
    if missing:
        raise ValueError(f"OpenAPI is missing workflow schemas: {', '.join(missing)}")

    lines = [
        "/**",
        " * Generated from FastAPI OpenAPI by scripts/generate_workflow_contracts.py.",
        " * Do not edit by hand; run the generator or its --check mode.",
        " */",
        "",
    ]
    for name in SCHEMA_NAMES:
        schema = schemas[name]
        if "enum" in schema:
            values = " | ".join(f'"{value}"' for value in schema["enum"])
            lines.extend([f"export type {name} = {values};", ""])
            continue

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for property_name, property_schema in properties.items():
            optional = "" if property_name in required else "?"
            lines.append(f"  {property_name}{optional}: {schema_type(property_schema)};")
        lines.extend(["}", ""])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if output differs")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "packages" / "contracts" / "src" / "workflow.ts",
        help="output path (defaults to packages/contracts/src/workflow.ts)",
    )
    args = parser.parse_args()
    expected = render(create_app().openapi())

    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"generated contract is missing: {args.output}", file=sys.stderr)
            return 1
        if actual != expected:
            print(f"generated contract is out of date: {args.output}", file=sys.stderr)
            return 1
        print(f"workflow contract is up to date: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"generated workflow contract: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
