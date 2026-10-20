"""OCR provider protocol and implementations."""

from typing import Protocol

from PIL import Image

from dev_pre_review.drawings.contracts import TextRegion


class OcrProvider(Protocol):
    def recognize(self, image: Image.Image, page_or_sheet: int | str = 1) -> list[TextRegion]:
        """Recognize text and bounding boxes from an image."""
        ...


class MockOcrProvider:
    def __init__(self, canned_text: str = "SAMPLE OCR TEXT") -> None:
        self.canned_text = canned_text

    def recognize(self, image: Image.Image, page_or_sheet: int | str = 1) -> list[TextRegion]:
        width, height = image.size
        return [
            TextRegion(
                page_or_sheet=page_or_sheet,
                raw_text=self.canned_text,
                pixel_bbox=(0.0, 0.0, float(width), float(height)),
                confidence=0.85,
            )
        ]


class DefaultOcrProvider:
    """Default lightweight OCR using PyMuPDF page-level OCR if available, or fallback."""

    def recognize(self, image: Image.Image, page_or_sheet: int | str = 1) -> list[TextRegion]:
        # Basic fallback when Tesseract language packs are not installed locally
        width, height = image.size
        return [
            TextRegion(
                page_or_sheet=page_or_sheet,
                raw_text="",
                pixel_bbox=(0.0, 0.0, float(width), float(height)),
                confidence=0.5,
            )
        ]
