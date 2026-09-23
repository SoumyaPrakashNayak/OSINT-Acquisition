"""Phase 4: Web Content Extraction package."""

from app.extraction.errors import (
    EMPTY_HTML,
    EXTRACTION_FAILED,
    HTML_PARSE_ERROR,
    INVALID_DOCUMENT,
    UNSUPPORTED_DOCUMENT,
)
from app.extraction.extractor import ContentExtractor, DeterministicHtmlExtractor
from app.extraction.models import (
    ContentQuality,
    ExtractedDocument,
    ExtractionError,
    ExtractionRequest,
    ExtractionResult,
    HeadingItem,
    LinkItem,
)
from app.extraction.service import ExtractionService

__all__ = [
    "ContentQuality",
    "HeadingItem",
    "LinkItem",
    "ExtractedDocument",
    "ExtractionError",
    "ExtractionResult",
    "ExtractionRequest",
    "ContentExtractor",
    "DeterministicHtmlExtractor",
    "ExtractionService",
    "EMPTY_HTML",
    "EXTRACTION_FAILED",
    "HTML_PARSE_ERROR",
    "INVALID_DOCUMENT",
    "UNSUPPORTED_DOCUMENT",
]
