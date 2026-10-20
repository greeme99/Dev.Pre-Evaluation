"""PyMuPDF-based PDF parser: vector text extraction, 300 DPI rendering, OCR fallback."""

from uuid import uuid4

import pymupdf
from PIL import Image

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import DrawingDocument, TextRegion
from dev_pre_review.models.ocr import DefaultOcrProvider, OcrProvider
from dev_pre_review.storage.files import StoredFile

TARGET_DPI = 300
PT_PER_INCH = 72.0
ZOOM_FACTOR = TARGET_DPI / PT_PER_INCH  # 4.1666...


class PdfParser:
    def __init__(self, ocr_provider: OcrProvider | None = None) -> None:
        self.ocr_provider = ocr_provider or DefaultOcrProvider()

    def parse(self, source: StoredFile) -> DrawingDocument:
        doc = pymupdf.open(source.path)  # type: ignore[no-untyped-call]
        page_count = doc.page_count

        all_regions: list[TextRegion] = []
        is_low_res = False
        profile = "vector_pdf"

        matrix = pymupdf.Matrix(ZOOM_FACTOR, ZOOM_FACTOR)  # type: ignore[no-untyped-call]

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc.load_page(page_idx)  # type: ignore[no-untyped-call]

            # 1. Try vector text extraction
            blocks = page.get_text("blocks")
            vector_text_len = 0
            page_vector_regions: list[TextRegion] = []

            for b in blocks:
                # b: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(b) >= 7 and b[6] == 0:  # text block
                    raw_text = str(b[4]).strip()
                    if raw_text:
                        vector_text_len += len(raw_text)
                        # Convert PDF point coords to 300 DPI pixel bbox
                        px_bbox = (
                            float(b[0]) * ZOOM_FACTOR,
                            float(b[1]) * ZOOM_FACTOR,
                            float(b[2]) * ZOOM_FACTOR,
                            float(b[3]) * ZOOM_FACTOR,
                        )
                        page_vector_regions.append(
                            TextRegion(
                                page_or_sheet=page_num,
                                raw_text=raw_text,
                                pixel_bbox=px_bbox,
                                confidence=1.0,
                            )
                        )

            if vector_text_len >= 20:
                all_regions.extend(page_vector_regions)
            else:
                # 2. Scanned image fallback with OCR
                profile = "scanned_pdf"

                # Check embedded image resolution
                img_list = page.get_images()
                page_rect = page.rect
                page_pt_w = page_rect.width
                page_pt_h = page_rect.height

                page_is_low_res = False
                if img_list:
                    # Check first image dimension
                    xref = img_list[0][0]
                    base_img = doc.extract_image(xref)  # type: ignore[no-untyped-call]
                    img_w = base_img.get("width", 0)
                    img_h = base_img.get("height", 0)
                    approx_dpi_w = (img_w / page_pt_w) * PT_PER_INCH if page_pt_w > 0 else 0
                    approx_dpi_h = (img_h / page_pt_h) * PT_PER_INCH if page_pt_h > 0 else 0
                    if approx_dpi_w < 150 or approx_dpi_h < 150:
                        page_is_low_res = True
                else:
                    page_is_low_res = True

                if page_is_low_res:
                    is_low_res = True

                # Render page at 300 DPI
                pix = page.get_pixmap(matrix=matrix)
                rendered_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                ocr_regions = self.ocr_provider.recognize(rendered_img, page_or_sheet=page_num)

                # Degrade confidence if low resolution
                adjusted_regions: list[TextRegion] = []
                for reg in ocr_regions:
                    conf = 0.4 if page_is_low_res else reg.confidence
                    adjusted_regions.append(reg.model_copy(update={"confidence": conf}))

                all_regions.extend(adjusted_regions)

        doc.close()  # type: ignore[no-untyped-call]

        metadata: dict[str, object] = {
            "profile": profile,
            "low_resolution": is_low_res,
        }

        return DrawingDocument(
            drawing_id=uuid4(),
            drawing_type=DrawingType.PDF,
            file_name=source.original_name,
            file_sha256=source.sha256,
            page_count=page_count,
            unit="mm",
            regions=all_regions,
            metadata=metadata,
        )
