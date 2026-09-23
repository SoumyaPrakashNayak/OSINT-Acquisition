"""Asynchronous HTTP web fetcher with redirect control, streaming size validation, and SSRF checks."""

from datetime import datetime, timezone
import hashlib
from typing import Protocol, runtime_checkable
from urllib.parse import urljoin
import httpx

from app.acquisition.errors import (
    CONNECTION_ERROR,
    CONTENT_TOO_LARGE,
    DNS_ERROR,
    FETCH_TIMEOUT,
    TLS_ERROR,
    TOO_MANY_REDIRECTS,
    UNSUPPORTED_CONTENT_TYPE,
    map_http_status_to_error,
)
from app.acquisition.models import AcquisitionError, FetchMetadata, FetchResult, WebDocument
from app.acquisition.url_policy import validate_url_policy
from app.discovery.url_utils import extract_domain
from app.logging_config import logger

SUPPORTED_MIME_TYPES = ("text/html", "application/xhtml+xml")


@runtime_checkable
class WebFetcher(Protocol):
    """Protocol defining the interface for acquiring raw web documents."""

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a candidate URL and return a structured FetchResult."""
        ...


class HttpWebFetcher(WebFetcher):
    """Production asynchronous HTTP fetcher utilizing httpx."""

    def __init__(
        self,
        timeout: float = 15.0,
        max_response_size_mb: int = 10,
        max_redirects: int = 5,
        user_agent: str = "SIRIS-OSINT-Component/0.1",
    ):
        self.timeout = timeout
        self.max_bytes = max_response_size_mb * 1024 * 1024
        self.max_redirects = max_redirects
        self.user_agent = user_agent

    async def fetch(self, url: str) -> FetchResult:
        """Acquire web content for a target URL safely."""
        requested_url = url.strip()
        retrieved_at = datetime.now(timezone.utc)

        # 1. Enforce initial URL security and SSRF policy
        is_allowed, error_code, error_msg = validate_url_policy(requested_url)
        if not is_allowed:
            logger.warning(f"URL policy rejected '{requested_url}': {error_code} - {error_msg}")
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(code=error_code or "INVALID_URL", message=error_msg or "URL blocked", retryable=False),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    retrieved_at=retrieved_at,
                ),
            )

        curr_url = requested_url
        redirect_count = 0
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
        client_timeout = httpx.Timeout(self.timeout, connect=min(self.timeout, 5.0))

        try:
            async with httpx.AsyncClient(timeout=client_timeout, verify=True) as client:
                while True:
                    try:
                        # Stream response so we can inspect headers and check size incrementally
                        async with client.stream(
                            "GET", curr_url, headers=headers, follow_redirects=False
                        ) as response:
                            status_code = response.status_code
                            raw_content_type = response.headers.get("content-type", "")
                            content_type = raw_content_type.split(";")[0].strip().lower() if raw_content_type else None

                            # Handle 3xx Redirects manually to enforce SSRF policy on every redirect target
                            if 300 <= status_code < 400 and "location" in response.headers:
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
                                            status_code=status_code,
                                            content_type=content_type,
                                            retrieved_at=datetime.now(timezone.utc),
                                        ),
                                    )

                                next_url = urljoin(curr_url, response.headers["location"])
                                # Validate redirect target against SSRF policy!
                                is_next_allowed, next_err_code, next_err_msg = validate_url_policy(next_url)
                                if not is_next_allowed:
                                    return FetchResult(
                                        success=False,
                                        document=None,
                                        error=AcquisitionError(
                                            code=next_err_code or "BLOCKED_PRIVATE_ADDRESS",
                                            message=f"Redirect target disallowed: {next_err_msg}",
                                            retryable=False,
                                        ),
                                        metadata=FetchMetadata(
                                            requested_url=requested_url,
                                            final_url=next_url,
                                            status_code=status_code,
                                            content_type=content_type,
                                            retrieved_at=datetime.now(timezone.utc),
                                        ),
                                    )
                                curr_url = next_url
                                continue  # Follow redirect

                            final_url = str(response.url) or curr_url
                            final_timestamp = datetime.now(timezone.utc)

                            # Handle non-2xx status codes (Controlled Acquisition Failure)
                            if not (200 <= status_code < 300):
                                err_code, err_msg, retryable = map_http_status_to_error(status_code)
                                return FetchResult(
                                    success=False,
                                    document=None,
                                    error=AcquisitionError(code=err_code, message=err_msg, retryable=retryable),
                                    metadata=FetchMetadata(
                                        requested_url=requested_url,
                                        final_url=final_url,
                                        status_code=status_code,
                                        content_type=content_type,
                                        retrieved_at=final_timestamp,
                                    ),
                                )

                            # Validate MIME content-type (only HTML is supported in Phase 3)
                            if not content_type or not any(content_type == ct for ct in SUPPORTED_MIME_TYPES):
                                return FetchResult(
                                    success=False,
                                    document=None,
                                    error=AcquisitionError(
                                        code=UNSUPPORTED_CONTENT_TYPE,
                                        message=f"Unsupported content type '{content_type or 'unknown'}'. Only HTML is supported.",
                                        retryable=False,
                                    ),
                                    metadata=FetchMetadata(
                                        requested_url=requested_url,
                                        final_url=final_url,
                                        status_code=status_code,
                                        content_type=content_type,
                                        retrieved_at=final_timestamp,
                                    ),
                                )

                            # Check declared Content-Length header if present
                            content_length_hdr = response.headers.get("content-length")
                            if content_length_hdr and content_length_hdr.isdigit():
                                if int(content_length_hdr) > self.max_bytes:
                                    return FetchResult(
                                        success=False,
                                        document=None,
                                        error=AcquisitionError(
                                            code=CONTENT_TOO_LARGE,
                                            message=f"Content-Length ({content_length_hdr} bytes) exceeds maximum limit ({self.max_bytes} bytes).",
                                            retryable=False,
                                        ),
                                        metadata=FetchMetadata(
                                            requested_url=requested_url,
                                            final_url=final_url,
                                            status_code=status_code,
                                            content_type=content_type,
                                            retrieved_at=final_timestamp,
                                        ),
                                    )

                            # Read response chunks safely enforcing size limit
                            body_chunks: list[bytes] = []
                            total_downloaded = 0
                            async for chunk in response.aiter_bytes():
                                total_downloaded += len(chunk)
                                if total_downloaded > self.max_bytes:
                                    return FetchResult(
                                        success=False,
                                        document=None,
                                        error=AcquisitionError(
                                            code=CONTENT_TOO_LARGE,
                                            message=f"Response body exceeded maximum allowed size ({self.max_bytes} bytes).",
                                            retryable=False,
                                        ),
                                        metadata=FetchMetadata(
                                            requested_url=requested_url,
                                            final_url=final_url,
                                            status_code=status_code,
                                            content_type=content_type,
                                            retrieved_at=final_timestamp,
                                        ),
                                    )
                                body_chunks.append(chunk)

                            content_bytes = b"".join(body_chunks)
                            # Decode HTML
                            encoding = response.encoding or "utf-8"
                            try:
                                html_text = content_bytes.decode(encoding, errors="replace")
                            except Exception:
                                html_text = content_bytes.decode("utf-8", errors="replace")

                            content_hash = hashlib.sha256(content_bytes).hexdigest()
                            domain = extract_domain(final_url)

                            document = WebDocument(
                                requested_url=requested_url,
                                final_url=final_url,
                                domain=domain,
                                status_code=status_code,
                                content_type=content_type,
                                content_length=len(content_bytes),
                                html=html_text,
                                retrieved_at=final_timestamp,
                                content_hash=content_hash,
                            )

                            return FetchResult(
                                success=True,
                                document=document,
                                error=None,
                                metadata=None,
                            )
                    except httpx.HTTPStatusError as e:
                        return FetchResult(
                            success=False,
                            document=None,
                            error=AcquisitionError(
                                code=map_http_status_to_error(e.response.status_code)[0],
                                message=str(e),
                                retryable=map_http_status_to_error(e.response.status_code)[2],
                            ),
                            metadata=FetchMetadata(
                                requested_url=requested_url,
                                final_url=curr_url,
                                status_code=e.response.status_code,
                                retrieved_at=datetime.now(timezone.utc),
                            ),
                        )
        except httpx.TimeoutException:
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(
                    code=FETCH_TIMEOUT,
                    message="The remote server did not respond within the configured timeout.",
                    retryable=True,
                ),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    final_url=curr_url if curr_url != requested_url else None,
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
        except httpx.ConnectError as e:
            err_str = str(e).lower()
            code = DNS_ERROR if "getaddrinfo" in err_str or "name resolution" in err_str else CONNECTION_ERROR
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(
                    code=code,
                    message="Failed to establish connection to the remote host.",
                    retryable=True,
                ),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    final_url=None,
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
        except httpx.RequestError as e:
            err_str = str(e).lower()
            code = TLS_ERROR if "ssl" in err_str or "certificate" in err_str else CONNECTION_ERROR
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(
                    code=code,
                    message=f"Network request error: {type(e).__name__}",
                    retryable=False,
                ),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    final_url=None,
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
        except Exception as e:
            # Unhandled unexpected error inside fetcher
            logger.error(f"Unexpected fetcher error for '{requested_url}': {e}", exc_info=True)
            return FetchResult(
                success=False,
                document=None,
                error=AcquisitionError(
                    code=CONNECTION_ERROR,
                    message="An unexpected network error occurred during acquisition.",
                    retryable=True,
                ),
                metadata=FetchMetadata(
                    requested_url=requested_url,
                    final_url=None,
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
