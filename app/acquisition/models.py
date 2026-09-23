"""Pydantic models for Phase 3 web content acquisition."""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class FetchMetadata(BaseModel):
    """Metadata detailing the acquisition lifecycle and outcome."""

    requested_url: str = Field(..., description="Original URL requested for acquisition")
    final_url: str | None = Field(default=None, description="Final resolved URL after redirects")
    status_code: int | None = Field(default=None, description="HTTP status code received")
    content_type: str | None = Field(default=None, description="MIME content type header")
    retrieved_at: datetime = Field(..., description="UTC timestamp of the fetch attempt")


class WebDocument(BaseModel):
    """Normalized raw HTML document acquired from a public web source."""

    requested_url: str = Field(..., description="Original target URL")
    final_url: str = Field(..., description="Final URL after redirect resolution")
    domain: str = Field(..., description="Normalized host/domain of the final URL")
    status_code: int = Field(..., description="HTTP status code (2xx)")
    content_type: str = Field(..., description="MIME type of the content (e.g. text/html)")
    content_length: int = Field(..., description="Length of the raw HTML content in bytes")
    html: str = Field(..., description="Preserved unparsed raw HTML markup")
    retrieved_at: datetime = Field(..., description="UTC timestamp when content was fetched")
    content_hash: str = Field(..., description="SHA-256 cryptographic hash of raw content bytes")


class AcquisitionError(BaseModel):
    """Structured error descriptor for controlled acquisition failures."""

    code: str = Field(..., description="Machine-readable error category code")
    message: str = Field(..., description="Human-readable explanation of why acquisition failed")
    retryable: bool = Field(..., description="Whether a subsequent retry could reasonably succeed")
    details: dict[str, Any] | None = Field(
        default=None, description="Sanitized technical details or context"
    )


class FetchResult(BaseModel):
    """Consolidated result contract for a single URL acquisition."""

    success: bool = Field(..., description="True if raw HTML was successfully acquired")
    document: WebDocument | None = Field(
        default=None, description="Successfully acquired document, populated when success=True"
    )
    error: AcquisitionError | None = Field(
        default=None, description="Structured failure descriptor, populated when success=False"
    )
    metadata: FetchMetadata | None = Field(
        default=None, description="Lifecycle metadata, preserved on both success and controlled failures"
    )


class FetchRequest(BaseModel):
    """API request payload for single URL acquisition."""

    url: str = Field(..., description="Candidate public URL to fetch")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("Field 'url' must not be empty or blank")
        parsed = urlparse(trimmed)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Invalid URL '{trimmed}'. Must start with http:// or https://")
        return trimmed


class BatchFetchRequest(BaseModel):
    """API request payload for batch URL acquisition."""

    urls: list[str] = Field(..., description="List of candidate public URLs to fetch")

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Field 'urls' list must not be empty")
        validated = []
        for raw in v:
            trimmed = raw.strip() if isinstance(raw, str) else ""
            if not trimmed:
                continue
            parsed = urlparse(trimmed)
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"Invalid URL in batch: '{trimmed}'. Must start with http:// or https://")
            validated.append(trimmed)
        if not validated:
            raise ValueError("No valid URLs provided in batch")
        return validated


class BatchFetchItem(BaseModel):
    """Individual URL acquisition result within a batch."""

    url: str = Field(..., description="Target candidate URL")
    success: bool = Field(..., description="True if document was successfully acquired")
    document: WebDocument | None = Field(default=None, description="Acquired document if successful")
    error: AcquisitionError | None = Field(default=None, description="Acquisition failure if unsuccessful")
    metadata: FetchMetadata | None = Field(default=None, description="Acquisition metadata")


class AcquisitionBatchResponse(BaseModel):
    """Consolidated response payload for batch acquisition."""

    total: int = Field(..., description="Total URLs processed in this batch")
    successful: int = Field(..., description="Count of successfully acquired documents")
    failed: int = Field(..., description="Count of failed acquisition attempts")
    results: list[BatchFetchItem] = Field(
        default_factory=list, description="Per-URL acquisition results"
    )
