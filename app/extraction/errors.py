"""Structured error codes and domain exceptions for Phase 4 web content extraction."""

from typing import Any

# Error codes
INVALID_DOCUMENT = "INVALID_DOCUMENT"
EMPTY_HTML = "EMPTY_HTML"
HTML_PARSE_ERROR = "HTML_PARSE_ERROR"
EXTRACTION_FAILED = "EXTRACTION_FAILED"
UNSUPPORTED_DOCUMENT = "UNSUPPORTED_DOCUMENT"


class ExtractionException(Exception):
    """Domain exception raised internally during document extraction."""

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
