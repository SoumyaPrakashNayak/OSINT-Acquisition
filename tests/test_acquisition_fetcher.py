"""Tests for HTTP fetcher and FetchResult contract (Phase 3.1)."""

import pytest
from app.acquisition.errors import CONNECTION_ERROR, FETCH_TIMEOUT
from app.acquisition.mock_fetcher import MockWebFetcher


@pytest.mark.asyncio
async def test_successful_fetch():
    """Test 3.1.1: Successful fetch returns WebDocument with 200, HTML, and success=True."""
    fetcher = MockWebFetcher()
    url = "https://news.example.com/article"
    raw_html = "<!DOCTYPE html><html><body><h1>Investigation Target</h1></body></html>"
    fetcher.add_response(url, html=raw_html, status_code=200, content_type="text/html")

    result = await fetcher.fetch(url)
    assert result.success is True
    assert result.document is not None
    assert result.document.status_code == 200
    assert result.document.html == raw_html
    assert result.document.requested_url == url
    assert result.document.final_url == url
    assert result.error is None


@pytest.mark.asyncio
async def test_fetch_final_url_after_redirect():
    """Test 3.1.2: Requested URL and final URL are both preserved across redirects."""
    fetcher = MockWebFetcher()
    old_url = "https://example.com/old-link"
    new_url = "https://example.com/new-article"
    fetcher.add_redirect(old_url, new_url)
    fetcher.add_response(new_url, html="<html><body>Redirected</body></html>", status_code=200)

    result = await fetcher.fetch(old_url)
    assert result.success is True
    assert result.document is not None
    assert result.document.requested_url == old_url
    assert result.document.final_url == new_url


@pytest.mark.asyncio
async def test_fetch_timeout():
    """Test 3.1.3: Remote server timeout returns controlled failure with retryable=True."""
    fetcher = MockWebFetcher()
    url = "https://slow.example.com/hanging"
    fetcher.add_error(
        url,
        code=FETCH_TIMEOUT,
        message="The remote server did not respond within the configured timeout.",
        retryable=True,
    )

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == FETCH_TIMEOUT
    assert result.error.retryable is True
    assert result.metadata is not None
    assert result.metadata.requested_url == url


@pytest.mark.asyncio
async def test_fetch_connection_failure():
    """Test 3.1.4: Network failure returns controlled failure with CONNECTION_ERROR."""
    fetcher = MockWebFetcher()
    url = "https://unreachable.example.com/item"
    fetcher.add_error(
        url,
        code=CONNECTION_ERROR,
        message="Failed to connect to host.",
        retryable=True,
    )

    result = await fetcher.fetch(url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == CONNECTION_ERROR
    assert result.error.retryable is True
