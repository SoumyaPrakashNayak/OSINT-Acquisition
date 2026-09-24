"""Phase 5 — Named Entity Recognition (NER) and Entity Extraction."""

from app.entity_extraction.errors import (
    EMPTY_DOCUMENT,
    ENTITY_EXTRACTION_FAILED,
    INVALID_DOCUMENT,
    MODEL_UNAVAILABLE,
    UNSUPPORTED_DOCUMENT,
    EntityExtractionException,
)
from app.entity_extraction.extractor import (
    DeterministicEntityExtractor,
    EntityExtractor,
    split_sentences_with_spans,
)
from app.entity_extraction.mock_extractor import MockEntityExtractor
from app.entity_extraction.models import (
    EntityExtractionError,
    EntityExtractionMetrics,
    EntityExtractionRequest,
    EntityExtractionResult,
    EntityOccurrence,
    ExtractedEntity,
    UniqueEntity,
)
from app.entity_extraction.normalization import (
    normalize_date,
    normalize_email,
    normalize_entity,
    normalize_money,
    normalize_phone,
    normalize_time,
    normalize_url,
    normalize_whitespace,
)
from app.entity_extraction.service import EntityExtractionService
from app.entity_extraction.taxonomy import (
    ENTITY_TYPE_DESCRIPTIONS,
    EntityType,
    is_valid_entity_type,
)

__all__ = [
    "EntityType",
    "ENTITY_TYPE_DESCRIPTIONS",
    "is_valid_entity_type",
    "EntityOccurrence",
    "ExtractedEntity",
    "UniqueEntity",
    "EntityExtractionMetrics",
    "EntityExtractionError",
    "EntityExtractionResult",
    "EntityExtractionRequest",
    "EntityExtractor",
    "DeterministicEntityExtractor",
    "MockEntityExtractor",
    "split_sentences_with_spans",
    "EntityExtractionService",
    "normalize_whitespace",
    "normalize_email",
    "normalize_url",
    "normalize_phone",
    "normalize_money",
    "normalize_date",
    "normalize_time",
    "normalize_entity",
    "INVALID_DOCUMENT",
    "EMPTY_DOCUMENT",
    "ENTITY_EXTRACTION_FAILED",
    "MODEL_UNAVAILABLE",
    "UNSUPPORTED_DOCUMENT",
    "EntityExtractionException",
]
