"""Deterministic in-memory web fetcher for development and testing."""

import asyncio
from datetime import datetime, timezone
import hashlib
from app.acquisition.errors import (
    CONTENT_TOO_LARGE,
    FETCH_TIMEOUT,
    RETRYABLE_MAP,
    TOO_MANY_REDIRECTS,
    UNSUPPORTED_CONTENT_TYPE,
    map_http_status_to_error,
)
from app.acquisition.fetcher import WebFetcher
from app.acquisition.models import AcquisitionError, FetchMetadata, FetchResult, WebDocument
from app.acquisition.url_policy import validate_url_policy
from app.discovery.url_utils import extract_domain


class MockWebFetcher(WebFetcher):
    """Deterministic in-memory fetcher providing canned responses, redirects, and failure simulations."""

    def __init__(self, max_redirects: int = 5, delay: float = 0.0):
        self.max_redirects = max_redirects
        self.delay = delay
        self._responses: dict[str, dict] = {}
        self._errors: dict[str, AcquisitionError] = {}
        self._error_status_codes: dict[str, int] = {}
        self._redirects: dict[str, str] = {}
        self._active_fetches = 0
        self._max_observed_concurrency = 0

    def add_response(
        self,
        url: str,
        html: str = "<html><body><h1>Public Report</h1><p>Mock article body.</p></body></html>",
        status_code: int = 200,
        content_type: str = "text/html",
        final_url: str | None = None,
    ) -> None:
        """Register a canned successful or custom HTTP response."""
        self._responses[url.strip()] = {
            "html": html,
            "status_code": status_code,
            "content_type": content_type,
            "final_url": (final_url or url).strip(),
        }

    def add_error(
        self,
        url: str,
        code: str,
        message: str,
        retryable: bool | None = None,
        status_code: int | None = None,
    ) -> None:
        """Register a simulated acquisition error for a URL."""
        is_retryable = retryable if retryable is not None else RETRYABLE_MAP.get(code, False)
        self._errors[url.strip()] = AcquisitionError(
            code=code,
            message=message,
            retryable=is_retryable,
        )
        if status_code:
            self._error_status_codes[url.strip()] = status_code

    def add_redirect(self, from_url: str, to_url: str) -> None:
        """Register a redirect mapping."""
        self._redirects[from_url.strip()] = to_url.strip()

    async def fetch(self, url: str) -> FetchResult:
        """Execute deterministic mock fetch."""
        requested_url = url.strip()
        retrieved_at = datetime.now(timezone.utc)

        # Track concurrency for testing
        self._active_fetches += 1
        self._max_observed_concurrency = max(self._max_observed_concurrency, self._active_fetches)
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        self._active_fetches -= 1

        # 1. Enforce initial URL security and SSRF policy
        is_allowed, err_code, err_msg = validate_url_policy(requested_url)
        if not is_allowed:
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(
                    code=err_code or "INVALID_URL",
                    message=err_msg or "URL disallowed by policy",
                    retryable=False,
                ),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    retrieved_at=retrieved_at,
                ),
            )

        # 2. Check for redirect loop / chain
        curr_url = requested_url
        redirect_count = 0
        while curr_url in self._redirects:
            redirect_count += 1
            if redirect_count > self.max_redirects:
                return FetchResult(
                    success=False,
                    document=None,
                    error=AcquisitionError(
                        code=TOO_MANY_REDIRECTS,
                        message=f"Exceeded maximum allowed redirects ({self.max_redirects}).",
                        retryable=False,
                    ),
                    metadata=FetchMetadata(
                        requested_url=requested_url,
                        final_url=curr_url,
                        status_code=301,
                        retrieved_at=retrieved_at,
                    ),
                )
            curr_url = self._redirects[curr_url]
            # Check redirect destination policy
            is_dest_allowed, dest_err_code, dest_err_msg = validate_url_policy(curr_url)
            if not is_dest_allowed:
                return FetchResult(
                    success=False,
                    document=None,
                    error=AcquisitionError(
                        code=dest_err_code or "BLOCKED_PRIVATE_ADDRESS",
                        message=dest_err_msg or "Redirect destination disallowed",
                        retryable=False,
                    ),
                    metadata=FetchMetadata(
                        requested_url=requested_url,
                        final_url=curr_url,
                        status_code=301,
                        retrieved_at=retrieved_at,
                    ),
                )

        final_url = curr_url

        # 3. Check registered errors on initial URL or final resolved URL
        error_target = requested_url if requested_url in self._errors else (final_url if final_url in self._errors else None)
        if error_target:
            err = self._errors[error_target]
            status = self._error_status_codes.get(error_target)
            return FetchResult(
                success=False,
                document=None,
                error=err,
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    final_url=final_url if final_url != requested_url or status else None,
                    status_code=status,
                    content_type="text/html" if status and status != 408 else None,
                    retrieved_at=retrieved_at,
                ),
            )

        # 4. Check registered custom responses
        resp_target = requested_url if requested_url in self._responses else (final_url if final_url in self._responses else None)
        if resp_target:
            cfg = self._responses[resp_target]
            status_code = cfg["status_code"]
            content_type = cfg["content_type"]
            html = cfg["html"]
            resolved_final = cfg.get("final_url", final_url)

            # Check if custom response simulates error status
            if not (200 <= status_code < 300):
                code, msg, retry = map_http_status_to_error(status_code)
                return FetchResult(
                    success=False,
                    document=None,
                    error=AcquisitionError(code=code, message=msg, retryable=retry),
                    metadata=FetchMetadata(
                        requested_url=requested_url,
                        final_url=resolved_final,
                        status_code=status_code,
                        content_type=content_type,
                        retrieved_at=retrieved_at,
                    ),
                )

            # Check unsupported content type
            if "html" not in content_type.lower():
                return FetchResult(
                    success=False,
                    document=None,
                    error=AcquisitionError(
                        code=UNSUPPORTED_CONTENT_TYPE,
                        message=f"The resource is not a supported HTML document (got '{content_type}').",
                        retryable=False,
                    ),
                    metadata=FetchMetadata(
                        requested_url=requested_url,
                        final_url=resolved_final,
                        status_code=status_code,
                        content_type=content_type,
                        retrieved_at=retrieved_at,
                    ),
                )

            # Check oversized response simulation
            if len(html.encode("utf-8")) > 10 * 1024 * 1024:
                return FetchResult(
                    success=False,
                    document=None,
                    error=AcquisitionError(
                        code=CONTENT_TOO_LARGE,
                        message="The resource exceeds the maximum configured size limit.",
                        retryable=False,
                    ),
                    metadata=FetchMetadata(
                        requested_url=requested_url,
                        final_url=resolved_final,
                        status_code=status_code,
                        content_type=content_type,
                        retrieved_at=retrieved_at,
                    ),
                )

            content_bytes = html.encode("utf-8")
            doc = WebDocument(
                requested_url=requested_url,
                final_url=resolved_final,
                domain=extract_domain(resolved_final),
                status_code=status_code,
                content_type=content_type,
                content_length=len(content_bytes),
                html=html,
                retrieved_at=retrieved_at,
                content_hash=hashlib.sha256(content_bytes).hexdigest(),
            )
            return FetchResult(success=True, document=doc, error=None, metadata=None)

        # 5. Default deterministic synthetic response
        html = f"<!DOCTYPE html><html><head><title>Candidate Public Resource</title></head><body><h1>Record</h1><p>Publicly retrieved content for {requested_url}</p></body></html>"
        content_bytes = html.encode("utf-8")
        doc = WebDocument(
            requested_url=requested_url,
            final_url=final_url,
            domain=extract_domain(final_url),
            status_code=200,
            content_type="text/html",
            content_length=len(content_bytes),
            html=html,
            retrieved_at=retrieved_at,
            content_hash=hashlib.sha256(content_bytes).hexdigest(),
        )
        return FetchResult(success=True, document=doc, error=None, metadata=None)
