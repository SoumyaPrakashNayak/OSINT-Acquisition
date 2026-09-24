"""Pydantic schemas and domain models for Phase 5 Named Entity Recognition."""

from typing import Any
from pydantic import BaseModel, Field

from app.entity_extraction.taxonomy import EntityType
from app.extraction.models import ExtractedDocument


class EntityOccurrence(BaseModel):
    """An individual span occurrence of an entity mention in the source document."""

    text: str = Field(..., description="Exact mention text as it appears in document.text")
    start_offset: int = Field(..., ge=0, description="0-indexed start character offset in document.text")
    end_offset: int = Field(..., ge=0, description="0-indexed end character offset (exclusive) in document.text")
    sentence: str | None = Field(default=None, description="Exact containing sentence from source text")
    confidence: float | None = Field(default=None, description="Extraction confidence score if available")


class ExtractedEntity(BaseModel):
    """Normalized structured entity mention extracted from an ExtractedDocument."""

    id: str = Field(..., description="Deterministic unique identifier for this entity mention")
    type: EntityType = Field(..., description="Taxonomy classification of the entity")
    text: str = Field(..., description="Exact entity mention text as it appears in document.text")
    normalized_text: str = Field(..., description="Conservatively normalized entity text")
    start_offset: int = Field(..., ge=0, description="0-indexed start character offset in document.text")
    end_offset: int = Field(..., ge=0, description="0-indexed end character offset (exclusive) in document.text")
    sentence: str | None = Field(default=None, description="Exact containing sentence from source text")
    confidence: float | None = Field(default=None, description="Extraction confidence score if available, else null")
    source_document_hash: str = Field(..., description="SHA-256 hash of the authoritative source document")
    source_url: str | None = Field(default=None, description="Authoritative source URL of the document")


class UniqueEntity(BaseModel):
    """Grouped entity record deduplicating occurrences with identical type and normalized text."""

    type: EntityType = Field(..., description="Taxonomy classification of the entity")
    normalized_text: str = Field(..., description="Normalized representation common across occurrences")
    count: int = Field(..., ge=1, description="Number of times this exact entity is mentioned in the document")
    occurrences: list[EntityOccurrence] = Field(
        default_factory=list, description="All span occurrences of this entity in document order"
    )


class EntityExtractionMetrics(BaseModel):
    """Observational metrics measuring entity extraction workload and performance."""

    character_count: int = Field(default=0, description="Character count of document text analyzed")
    word_count: int = Field(default=0, description="Word count of document text analyzed")
    mention_count: int = Field(default=0, description="Total entity mentions extracted")
    unique_entity_count: int = Field(default=0, description="Total unique normalized entities")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")


class EntityExtractionError(BaseModel):
    """Descriptor for controlled extraction failures (Category B)."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of why extraction failed")
    retryable: bool = Field(default=False, description="Whether repeating extraction could succeed")
    details: dict[str, Any] | None = Field(
        default=None, description="Sanitized technical details or context"
    )


class EntityExtractionResult(BaseModel):
    """Result contract returned by the entity extraction service and API."""

    success: bool = Field(..., description="True if document was successfully processed for entities")
    document_hash: str | None = Field(default=None, description="SHA-256 content hash of source document")
    source_url: str | None = Field(default=None, description="Authoritative source URL of the document")
    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="All extracted entity mentions in document order"
    )
    unique_entities: list[UniqueEntity] = Field(
        default_factory=list, description="Deduplicated unique entities with occurrence records"
    )
    entity_count: int = Field(default=0, description="Total entity mentions extracted")
    mention_count: int = Field(default=0, description="Total entity mentions extracted")
    unique_entity_count: int = Field(default=0, description="Total unique normalized entities extracted")
    counts_by_type: dict[str, int] = Field(
        default_factory=dict, description="Deterministic counts of mentions grouped by entity type"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal notices or extraction caveats"
    )
    error: EntityExtractionError | None = Field(
        default=None, description="Extraction failure details if unsuccessful"
    )
    metrics: EntityExtractionMetrics | None = Field(
        default=None, description="Observational execution metrics"
    )


class EntityExtractionRequest(BaseModel):
    """API request payload for extracting entities from an ExtractedDocument."""

    document: ExtractedDocument = Field(
        ..., description="Authoritative ExtractedDocument produced during Phase 4"
    )
