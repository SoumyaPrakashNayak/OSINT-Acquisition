"""Tests for raw document normalization and cryptographic hashing (Phase 3.3)."""

import hashlib
import pytest
from app.acquisition.mock_fetcher import MockWebFetcher


@pytest.mark.asyncio
async def test_sha256_hash_calculation():
    """Test 3.3.1: Correct SHA-256 calculation for acquired HTML bytes."""
    fetcher = MockWebFetcher()
    url = "https://example.com/content"
    html = "<html>test</html>"
    fetcher.add_response(url, html=html, status_code=200)

    result = await fetcher.fetch(url)
    assert result.success is True
    assert result.document is not None
    expected_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    assert result.document.content_hash == expected_hash


@pytest.mark.asyncio
async def test_deterministic_hash_same_content():
    """Test 3.3.2: Identical content produces identical SHA-256 hashes."""
    fetcher = MockWebFetcher()
    url1 = "https://example.com/page1"
    url2 = "https://example.com/page2"
    identical_html = "<html><body>Consistent Content</body></html>"
    fetcher.add_response(url1, html=identical_html)
    fetcher.add_response(url2, html=identical_html)

    res1 = await fetcher.fetch(url1)
    res2 = await fetcher.fetch(url2)
    assert res1.document.content_hash == res2.document.content_hash


@pytest.mark.asyncio
async def test_different_content_different_hash():
    """Test 3.3.3: Different content produces different SHA-256 hashes."""
    fetcher = MockWebFetcher()
    url1 = "https://example.com/article-a"
    url2 = "https://example.com/article-b"
    fetcher.add_response(url1, html="<html>Content A</html>")
    fetcher.add_response(url2, html="<html>Content B</html>")

    res1 = await fetcher.fetch(url1)
    res2 = await fetcher.fetch(url2)
    assert res1.document.content_hash != res2.document.content_hash


@pytest.mark.asyncio
async def test_domain_extraction_from_final_url():
    """Test 3.3.4: Host domain is accurately extracted from final resolved URL."""
    fetcher = MockWebFetcher()
    url = "https://news.odisha.gov.in/portal/press-release"
    fetcher.add_response(url, html="<html><body>Press Release</body></html>")

    result = await fetcher.fetch(url)
    assert result.success is True
    assert result.document.domain == "news.odisha.gov.in"


@pytest.mark.asyncio
async def test_raw_html_preservation_without_extraction():
    """Test 3.3.5: Raw HTML tags and markup structure are strictly preserved without stripping."""
    fetcher = MockWebFetcher()
    url = "https://example.com/structured"
    raw_html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><title>Target Dossier</title></head>\n"
        "<body>\n"
        "  <h1>Ramesh Kumar</h1>\n"
        "  <p>Associated with <strong>ABC Ltd</strong> in Bhubaneswar.</p>\n"
        "</body>\n"
        "</html>"
    )
    fetcher.add_response(url, html=raw_html)

    result = await fetcher.fetch(url)
    assert result.success is True
    # HTML must remain unparsed and identical to source
    assert result.document.html == raw_html
    assert "<h1>Ramesh Kumar</h1>" in result.document.html
    assert "<strong>ABC Ltd</strong>" in result.document.html
