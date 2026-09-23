"""Tests for redirect tracking, limits, and security."""

import pytest
from app.acquisition.errors import BLOCKED_PRIVATE_ADDRESS, TOO_MANY_REDIRECTS
from app.acquisition.mock_fetcher import MockWebFetcher


@pytest.mark.asyncio
async def test_normal_redirect_followed():
    """Test 3.5.1: Legitimate redirects are followed; requested and final URLs are tracked."""
    fetcher = MockWebFetcher(max_redirects=5)
    url_a = "https://example.com/start"
    url_b = "https://example.com/middle"
    url_c = "https://example.com/final-destination"

    fetcher.add_redirect(url_a, url_b)
    fetcher.add_redirect(url_b, url_c)
    fetcher.add_response(url_c, html="<html><body>Final Content</body></html>")

    result = await fetcher.fetch(url_a)
    assert result.success is True
    assert result.document is not None
    assert result.document.requested_url == url_a
    assert result.document.final_url == url_c


@pytest.mark.asyncio
async def test_redirect_limit_exceeded():
    """Test 3.5.2: Redirect chains exceeding max_redirects return TOO_MANY_REDIRECTS."""
    fetcher = MockWebFetcher(max_redirects=3)
    # Create a 4-hop redirect chain
    fetcher.add_redirect("https://example.com/r0", "https://example.com/r1")
    fetcher.add_redirect("https://example.com/r1", "https://example.com/r2")
    fetcher.add_redirect("https://example.com/r2", "https://example.com/r3")
    fetcher.add_redirect("https://example.com/r3", "https://example.com/r4")

    result = await fetcher.fetch("https://example.com/r0")
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == TOO_MANY_REDIRECTS
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_redirect_to_private_address_blocked():
    """Verify an external redirect pointing to a private or loopback IP is blocked."""
    fetcher = MockWebFetcher()
    public_url = "https://example.com/malicious-redirect"
    private_target = "http://127.0.0.1:8080/admin"
    fetcher.add_redirect(public_url, private_target)

    result = await fetcher.fetch(public_url)
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == BLOCKED_PRIVATE_ADDRESS
