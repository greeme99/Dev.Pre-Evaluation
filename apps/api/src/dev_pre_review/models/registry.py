"""Model and provider registry."""

from dev_pre_review.models.ocr import DefaultOcrProvider, OcrProvider


class ModelRegistry:
    def __init__(self) -> None:
        self._ocr_provider: OcrProvider = DefaultOcrProvider()

    def get_ocr_provider(self) -> OcrProvider:
        return self._ocr_provider

    def set_ocr_provider(self, provider: OcrProvider) -> None:
        self._ocr_provider = provider


default_model_registry = ModelRegistry()
