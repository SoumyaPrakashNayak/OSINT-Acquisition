"""Structured errors and exceptions for Phase 5 entity extraction."""

from typing import Any

# Error codes for Category B controlled failures
INVALID_DOCUMENT = "INVALID_DOCUMENT"
EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
ENTITY_EXTRACTION_FAILED = "ENTITY_EXTRACTION_FAILED"
MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
UNSUPPORTED_DOCUMENT = "UNSUPPORTED_DOCUMENT"


class EntityExtractionException(Exception):
    """Domain exception raised during controlled entity extraction failures."""

    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details
