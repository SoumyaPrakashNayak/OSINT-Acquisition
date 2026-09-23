"""Tests for URL validation, domain extraction, and normalization (Phase 2)."""

import pytest
from app.discovery.url_utils import extract_domain, is_valid_url, normalize_url


@pytest.mark.parametrize(
    "valid_url",
    [
        "https://example.com/article",
        "http://example.com/article",
        "https://sub.domain.org/path/to/page?param=value",
        "http://192.168.1.1/info",
    ],
)
def test_valid_url_passes(valid_url: str):
    """Test 2.3a: Valid HTTP and HTTPS URLs pass validation."""
    assert is_valid_url(valid_url) is True


@pytest.mark.parametrize(
    "invalid_url",
    [
        "not-a-url",
        "ftp://example.com/file",
        "file:///local/path",
        "javascript:alert(1)",
        "",
        "   ",
        None,
    ],
)
def test_invalid_url_fails(invalid_url: str | None):
    """Test 2.3b: Invalid or non-http/https URLs fail validation."""
    assert is_valid_url(invalid_url) is False


def test_domain_extraction():
    """Test 2.4: Domain extraction from URLs."""
    assert extract_domain("https://example.com/news/ramesh") == "example.com"
    assert extract_domain("http://odisha.gov.in/portal") == "odisha.gov.in"
    assert extract_domain("https://sub.press.example.org:8080/article") == "sub.press.example.org"
    assert extract_domain("invalid-url") == ""


def test_url_normalization_tracking_params_removed():
    """Test that marketing and tracking parameters are stripped while functional params remain."""
    raw = "https://example.com/news/item/?utm_source=twitter&utm_medium=social&article_id=987&fbclid=XYZ123#top"
    normalized = normalize_url(raw)
    assert "utm_source" not in normalized
    assert "utm_medium" not in normalized
    assert "fbclid" not in normalized
    assert "article_id=987" in normalized
    assert "#top" not in normalized
    assert normalized == "https://example.com/news/item?article_id=987"


def test_url_normalization_casing_and_trailing_slashes():
    """Test normalization lowercases domain and trims trailing slash."""
    url1 = "HTTPS://EXAMPLE.COM/articles/ramesh/"
    url2 = "https://example.com/articles/ramesh"
    assert normalize_url(url1) == normalize_url(url2)
