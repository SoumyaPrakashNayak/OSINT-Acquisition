"""Structured error schemas and domain exceptions."""

from typing import Any
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error payload."""

    code: str = Field(..., description="Machine-readable error category code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: dict[str, Any] | list[Any] | None = Field(
        default=None, description="Optional additional context (sanitized)"
    )


class OSINTError(BaseModel):
    """Standardized top-level error response model."""

    error: ErrorDetail


class OSINTException(Exception):
    """Base exception for OSINT Intelligence Component errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | list[Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class InvalidTargetException(OSINTException):
    """Raised when TargetPerson input validation fails."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(
            code="INVALID_TARGET",
            message=message,
            status_code=422,
            details=details,
        )


class SearchProviderException(OSINTException):
    """Raised when a search provider fails or returns an error."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(
            code="SEARCH_PROVIDER_ERROR",
            message=message,
            status_code=502,
            details=details,
        )


class SearchTimeoutException(OSINTException):
    """Raised when a search request times out."""

    def __init__(self, message: str = "Search provider request timed out", details: Any = None):
        super().__init__(
            code="SEARCH_TIMEOUT",
            message=message,
            status_code=504,
            details=details,
        )


class InvalidSearchResultException(OSINTException):
    """Raised when an external result contains malformed data."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(
            code="INVALID_SEARCH_RESULT",
            message=message,
            status_code=502,
            details=details,
        )
