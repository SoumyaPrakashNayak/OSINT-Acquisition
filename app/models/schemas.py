"""Pydantic schemas for the OSINT Intelligence Component."""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class TargetPerson(BaseModel):
    """Schema representing an individual targeted for OSINT investigation."""

    name: str = Field(..., description="Full or primary known name of the target person")
    aliases: list[str] = Field(
        default_factory=list,
        description="Known aliases, alternate spellings, or monikers",
    )
    phone: str | None = Field(
        default=None,
        description="Known phone number or contact string",
    )
    location: str | None = Field(
        default=None,
        description="Known geographical location, city, or state",
    )
    organization: str | None = Field(
        default=None,
        description="Known employer, company, political entity, or gang/group",
    )
    username: str | None = Field(
        default=None,
        description="Known social media username or handle",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Contextual investigation keywords or tags",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("Target person 'name' must not be empty or blank")
        return trimmed

    @field_validator("aliases", "keywords", mode="before")
    @classmethod
    def clean_string_list(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list):
            cleaned: list[str] = []
            for item in v:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        cleaned.append(s)
            return cleaned
        return []

    @field_validator("phone", "location", "organization", "username", mode="before")
    @classmethod
    def sanitize_optional_string(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            trimmed = v.strip()
            return trimmed if trimmed else None
        return str(v).strip() or None


class SearchResult(BaseModel):
    """Normalized public web/news search discovery result."""

    title: str = Field(..., description="Headline or title of the discovered content")
    url: str = Field(..., description="Fully-qualified candidate URL")
    source: str | None = Field(
        default=None,
        description="Originating news source, domain name, or platform",
    )
    snippet: str | None = Field(
        default=None,
        description="Summary text or snippet provided by search provider",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Publication timestamp if available",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("SearchResult 'title' must not be empty")
        return trimmed

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("SearchResult 'url' must not be empty")
        parsed = urlparse(trimmed)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Invalid URL format: '{trimmed}'. Must start with http:// or https://")
        return trimmed


class DiscoveryResponse(BaseModel):
    """Consolidated response payload for the /osint/discover endpoint."""

    target: TargetPerson
    queries: list[str] = Field(
        default_factory=list,
        description="Deterministic search queries executed during discovery",
    )
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Normalized, deduplicated candidate search results",
    )
    total_results: int = Field(
        default=0,
        description="Total count of candidate results discovered",
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Non-fatal warnings or search provider execution notices",
    )
