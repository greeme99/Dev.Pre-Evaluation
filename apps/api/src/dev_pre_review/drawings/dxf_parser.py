"""ezdxf-based DXF parser: modelspace/paperspace entity extraction and quality gate."""

from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import ezdxf
from pydantic import BaseModel, ConfigDict, Field

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import DrawingDocument, TextRegion
from dev_pre_review.storage.files import StoredFile


class DxfQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_blocked: bool
    missing_xrefs: list[str] = Field(default_factory=list)
    missing_fonts: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class DxfQualityGate:
    def inspect(self, doc: DrawingDocument) -> DxfQualityReport:
        missing_xrefs = [str(x) for x in doc.metadata.get("missing_xrefs", [])]
        missing_fonts = [str(f) for f in doc.metadata.get("missing_fonts", [])]

        reasons: list[str] = []
        if missing_xrefs:
            reasons.append(f"Missing external references (XREF): {', '.join(missing_xrefs)}")
        if missing_fonts:
            reasons.append(f"Missing required CAD fonts: {', '.join(missing_fonts)}")

        is_blocked = bool(missing_xrefs or missing_fonts)
        return DxfQualityReport(
            is_blocked=is_blocked,
            missing_xrefs=missing_xrefs,
            missing_fonts=missing_fonts,
            reasons=reasons,
        )


class DxfParser:
    def parse(self, source: StoredFile) -> DrawingDocument:
        dxf_doc = ezdxf.readfile(source.path)  # type: ignore[attr-defined]

        regions: list[TextRegion] = []
        entity_counts: Counter[str] = Counter()

        # 1. Inspect modelspace
        msp = dxf_doc.modelspace()
        self._extract_space_entities(msp, "modelspace", regions, entity_counts)

        # 2. Inspect paperspace layouts
        paperspace_count = 0
        for layout in dxf_doc.layouts:
            if layout.name != "Model":
                paperspace_count += 1
                self._extract_space_entities(layout, layout.name, regions, entity_counts)

        # 3. Inspect XREFs
        missing_xrefs: list[str] = []
        source_dir = Path(source.path).parent
        for block in dxf_doc.blocks:
            block_entity = getattr(block, "block", None)
            is_xref = getattr(block, "is_xref", False) or (
                block_entity and getattr(block_entity, "is_xref", False)
            )
            if is_xref:
                xref_path = getattr(block.dxf, "xref_path", "") or (
                    getattr(block_entity.dxf, "xref_path", "") if block_entity else ""
                )
                if xref_path:
                    # Check if file exists in source directory or absolute
                    resolved = Path(xref_path)
                    if not resolved.is_absolute():
                        resolved = source_dir / xref_path
                    if not resolved.exists():
                        missing_xrefs.append(xref_path)

        # 4. Inspect Fonts
        missing_fonts: list[str] = []
        for style in dxf_doc.styles:
            font_file = getattr(style.dxf, "font", "")
            if font_file and font_file.lower().endswith(".shx"):
                # Missing specialized AutoCAD SHX shape fonts
                font_path = source_dir / font_file
                if not font_path.exists():
                    missing_fonts.append(font_file)

        is_blocked = bool(missing_xrefs or missing_fonts)

        metadata: dict[str, Any] = {
            "entity_counts": dict(entity_counts),
            "modelspace_count": 1,
            "paperspace_count": paperspace_count,
            "missing_xrefs": missing_xrefs,
            "missing_fonts": missing_fonts,
            "quality_blocked": is_blocked,
        }

        return DrawingDocument(
            drawing_id=uuid4(),
            drawing_type=DrawingType.DXF,
            file_name=source.original_name,
            file_sha256=source.sha256,
            page_count=1 + paperspace_count,
            unit="mm",
            regions=regions,
            metadata=metadata,
        )

    def _extract_space_entities(
        self,
        space: Any,
        space_name: str,
        regions: list[TextRegion],
        counts: Counter[str],
    ) -> None:
        for entity in space:
            dxftype = entity.dxftype()
            counts[dxftype] += 1

            if dxftype == "TEXT":
                raw_text = getattr(entity.dxf, "text", "").strip()
                if raw_text:
                    insert = getattr(entity.dxf, "insert", (0.0, 0.0))
                    height = float(getattr(entity.dxf, "height", 2.5))
                    cad_bbox = (
                        float(insert[0]),
                        float(insert[1]),
                        float(insert[0]) + len(raw_text) * height * 0.6,
                        float(insert[1]) + height,
                    )
                    regions.append(
                        TextRegion(
                            page_or_sheet=space_name,
                            raw_text=raw_text,
                            cad_bbox=cad_bbox,
                            layer=getattr(entity.dxf, "layer", None),
                            confidence=1.0,
                        )
                    )

            elif dxftype == "MTEXT":
                try:
                    raw_text = entity.plain_text().strip()
                except Exception:
                    raw_text = getattr(entity.dxf, "text", "").strip()
                if raw_text:
                    insert = getattr(entity.dxf, "insert", (0.0, 0.0))
                    height = float(getattr(entity.dxf, "char_height", 2.5))
                    cad_bbox = (
                        float(insert[0]),
                        float(insert[1]),
                        float(insert[0]) + len(raw_text) * height * 0.6,
                        float(insert[1]) + height,
                    )
                    regions.append(
                        TextRegion(
                            page_or_sheet=space_name,
                            raw_text=raw_text,
                            cad_bbox=cad_bbox,
                            layer=getattr(entity.dxf, "layer", None),
                            confidence=1.0,
                        )
                    )

            elif dxftype == "DIMENSION":
                raw_text = getattr(entity.dxf, "text", "").strip()
                if raw_text:
                    regions.append(
                        TextRegion(
                            page_or_sheet=space_name,
                            raw_text=raw_text,
                            layer=getattr(entity.dxf, "layer", None),
                            unit="mm",
                            confidence=1.0,
                        )
                    )
