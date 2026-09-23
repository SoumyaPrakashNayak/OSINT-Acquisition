"""Pydantic models for Phase 4 web content extraction."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from app.acquisition.models import WebDocument


class ContentQuality(str, Enum):
    """Deterministic classification of extraction usefulness based on content volume."""

    EMPTY = "EMPTY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HeadingItem(BaseModel):
    """Structured heading element extracted from HTML."""

    level: int = Field(..., ge=1, le=6, description="Heading level (1 to 6)")
    text: str = Field(..., description="Normalized text of the heading")


class LinkItem(BaseModel):
    """Hyperlink extracted and resolved from HTML content."""

    text: str = Field(..., description="Normalized link anchor text or title")
    url: str = Field(..., description="Fully-qualified resolved HTTP/HTTPS URL")


class ExtractedDocument(BaseModel):
    """Normalized structured representation of content extracted from a WebDocument."""

    # Provenance preserved from Phase 3 acquisition
    requested_url: str = Field(..., description="Original URL requested for acquisition")
    final_url: str = Field(..., description="Final URL after redirect resolution")
    domain: str = Field(..., description="Host domain extracted from final_url")
    content_hash: str = Field(..., description="SHA-256 hash of the authoritative raw HTML")
    retrieved_at: datetime = Field(..., description="UTC acquisition timestamp from WebDocument")

    # Document Metadata
    title: str | None = Field(default=None, description="Extracted page or article title")
    description: str | None = Field(default=None, description="Extracted meta or OpenGraph description")
    canonical_url: str | None = Field(default=None, description="Resolved canonical link URL")
    author: str | None = Field(default=None, description="Extracted byline or author name")
    publication_date: str | None = Field(
        default=None, description="Extracted publication date in ISO-8601 format"
    )
    modified_date: str | None = Field(
        default=None, description="Extracted modification date in ISO-8601 format"
    )
    language: str | None = Field(default=None, description="Document language code (e.g. en, en-US)")

    # Structured Content
    headings: list[HeadingItem] = Field(
        default_factory=list, description="Ordered document headings (h1-h6)"
    )
    paragraphs: list[str] = Field(
        default_factory=list, description="Extracted primary article/body paragraphs"
    )
    text: str = Field(
        default="", description="Clean visible article text joined by paragraph breaks"
    )
    links: list[LinkItem] = Field(
        default_factory=list, description="Extracted hyperlinks with resolved URLs"
    )

    # Content Quality & Metrics
    content_length: int = Field(default=0, description="Character count of extracted visible text")
    word_count: int = Field(default=0, description="Count of meaningful words in extracted text")
    character_count: int = Field(default=0, description="Total characters in extracted text")
    paragraph_count: int = Field(default=0, description="Total extracted paragraphs")
    heading_count: int = Field(default=0, description="Total extracted headings")
    link_count: int = Field(default=0, description="Total extracted hyperlinks")

    extraction_method: str = Field(
        default="deterministic_html",
        description="Deterministic strategy identifier used for extraction",
    )
    content_quality: ContentQuality = Field(
        default=ContentQuality.EMPTY,
        description="Quality classification based on word volume",
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal notices or extraction caveats"
    )


class ExtractionError(BaseModel):
    """Descriptor for controlled extraction failures."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of why extraction failed")
    retryable: bool = Field(default=False, description="Whether repeating extraction could succeed")
    details: dict[str, Any] | None = Field(
        default=None, description="Sanitized technical details or context"
    )


class ExtractionResult(BaseModel):
    """Result contract returned by the extraction service."""

    success: bool = Field(..., description="True if document was successfully extracted")
    document: ExtractedDocument | None = Field(
        default=None, description="Structured extracted document if successful"
    )
    error: ExtractionError | None = Field(
        default=None, description="Extraction failure details if unsuccessful"
    )


class ExtractionRequest(BaseModel):
    """API request payload for extracting content from an acquired WebDocument."""

    web_document: WebDocument = Field(
        ..., description="Authoritative WebDocument acquired during Phase 3"
    )
