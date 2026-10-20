"""Drawing parser protocol and registry."""

from typing import Protocol

from dev_pre_review.domain.enums import DrawingType
from dev_pre_review.drawings.contracts import DrawingDocument
from dev_pre_review.storage.files import StoredFile


class DrawingParser(Protocol):
    def parse(self, source: StoredFile) -> DrawingDocument:
        """Parse stored drawing file into standardized DrawingDocument."""
        ...


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[DrawingType, DrawingParser] = {}

    def register(self, drawing_type: DrawingType, parser: DrawingParser) -> None:
        self._parsers[drawing_type] = parser

    def get(self, drawing_type: DrawingType) -> DrawingParser:
        if drawing_type not in self._parsers:
            raise KeyError(f"No parser registered for drawing type: {drawing_type}")
        return self._parsers[drawing_type]


# Global default registry instance
default_registry = ParserRegistry()
