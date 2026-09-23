"""Tests for response validation and controlled failure handling (Phase 3.2)."""

import pytest
from app.acquisition.errors import (
    CONTENT_TOO_LARGE,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_RATE_LIMITED,
    HTTP_SERVER_ERROR,
    UNSUPPORTED_CONTENT_TYPE,
)
from app.acquisition.mock_fetcher import MockWebFetcher


@pytest.mark.asyncio
async def test_404_not_found_controlled_failure():
    """Test 3.2.1: HTTP 404 produces controlled failure with HTTP_NOT_FOUND and retryable=False."""
    fetcher = MockWebFetcher()
    url = "https://example.com/missing"
    fetcher.add_response(url, status_code=404)

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == HTTP_NOT_FOUND
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_403_forbidden_controlled_failure():
    """Test 3.2.2: HTTP 403 produces controlled failure with HTTP_FORBIDDEN and retryable=False."""
    fetcher = MockWebFetcher()
    url = "https://example.com/protected"
    fetcher.add_response(url, status_code=403)

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == HTTP_FORBIDDEN
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_429_rate_limited_controlled_failure():
    """Test 3.2.3: HTTP 429 produces controlled failure with HTTP_RATE_LIMITED and retryable=True."""
    fetcher = MockWebFetcher()
    url = "https://example.com/rate-limited"
    fetcher.add_response(url, status_code=429)

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == HTTP_RATE_LIMITED
    assert result.error.retryable is True


@pytest.mark.asyncio
async def test_500_server_error_controlled_failure():
    """Test 3.2.4: HTTP 500 produces controlled failure with HTTP_SERVER_ERROR and retryable=True."""
    fetcher = MockWebFetcher()
    url = "https://example.com/server-error"
    fetcher.add_response(url, status_code=500)

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == HTTP_SERVER_ERROR
    assert result.error.retryable is True


@pytest.mark.asyncio
async def test_unsupported_content_type():
    """Test 3.2.5: Non-HTML MIME type (e.g. application/pdf) returns UNSUPPORTED_CONTENT_TYPE."""
    fetcher = MockWebFetcher()
    url = "https://example.com/document.pdf"
    fetcher.add_response(url, html="%PDF-1.4...", status_code=200, content_type="application/pdf")

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == UNSUPPORTED_CONTENT_TYPE
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_oversized_content_rejection():
    """Test 3.2.6: Response body larger than max limit returns CONTENT_TOO_LARGE."""
    fetcher = MockWebFetcher()
    url = "https://example.com/huge-file.html"
    huge_html = "x" * (11 * 1024 * 1024)  # 11 MB exceeds 10 MB limit
    fetcher.add_response(url, html=huge_html, status_code=200)

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == CONTENT_TOO_LARGE
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_failure_metadata_preservation():
    """Test 3.2.7: Controlled failure preserves requested_url, final_url, status_code, and timestamps."""
    fetcher = MockWebFetcher()
    url = "https://example.com/forbidden-page"
    fetcher.add_response(url, status_code=403, content_type="text/html")

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.metadata is not None
    assert result.metadata.requested_url == url
    assert result.metadata.status_code == 403
    assert result.metadata.content_type == "text/html"
    assert result.metadata.retrieved_at is not None
