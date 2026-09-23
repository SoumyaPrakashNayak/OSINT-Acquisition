"""Tests for URL security policy and SSRF protections."""

import pytest
from app.acquisition.errors import BLOCKED_PRIVATE_ADDRESS, INVALID_URL
from app.acquisition.mock_fetcher import MockWebFetcher
from app.acquisition.url_policy import validate_url_policy


def test_https_allowed():
    """Test 3.4.1: HTTPS scheme is permitted."""
    allowed, code, _ = validate_url_policy("https://example.com/article")
    assert allowed is True
    assert code is None


def test_http_allowed():
    """Test 3.4.2: HTTP scheme is permitted."""
    allowed, code, _ = validate_url_policy("http://example.com/article")
    assert allowed is True
    assert code is None


def test_file_scheme_rejected():
    """Test 3.4.3: file:// URLs are rejected for security."""
    allowed, code, _ = validate_url_policy("file:///etc/passwd")
    assert allowed is False
    assert code == INVALID_URL


def test_localhost_rejected():
    """Test 3.4.4: localhost is blocked as a local/private host."""
    allowed, code, _ = validate_url_policy("http://localhost/admin")
    assert allowed is False
    assert code == BLOCKED_PRIVATE_ADDRESS


def test_loopback_ip_rejected():
    """Test 3.4.5: 127.0.0.1 loopback address is blocked."""
    allowed, code, _ = validate_url_policy("http://127.0.0.1:8000/internal")
    assert allowed is False
    assert code == BLOCKED_PRIVATE_ADDRESS


@pytest.mark.parametrize(
    "private_ip",
    [
        "http://10.0.0.1/status",
        "http://192.168.1.1/router",
        "http://172.16.0.1/dashboard",
        "http://172.31.255.255/secret",
    ],
)
def test_private_ipv4_rejected(private_ip: str):
    """Test 3.4.6: RFC 1918 private IPv4 ranges are blocked."""
    allowed, code, _ = validate_url_policy(private_ip)
    assert allowed is False
    assert code == BLOCKED_PRIVATE_ADDRESS


def test_link_local_address_rejected():
    """Test 3.4.7: AWS/cloud metadata and link-local address 169.254.169.254 is blocked."""
    allowed, code, _ = validate_url_policy("http://169.254.169.254/latest/meta-data")
    assert allowed is False
    assert code == BLOCKED_PRIVATE_ADDRESS


@pytest.mark.parametrize(
    "unsupported_scheme",
    [
        "ftp://ftp.example.com/file.txt",
        "javascript:alert(1)",
        "data:text/html,<h1>test</h1>",
        "blob:https://example.com/uuid",
    ],
)
def test_unsupported_schemes_rejected(unsupported_scheme: str):
    """Test 3.4.8: Non-HTTP/HTTPS schemes are rejected."""
    allowed, code, _ = validate_url_policy(unsupported_scheme)
    assert allowed is False
    assert code == INVALID_URL


@pytest.mark.asyncio
async def test_fetcher_integrates_url_policy_check():
    """Verify fetcher returns controlled failure when encountering an SSRF target."""
    fetcher = MockWebFetcher()
    result = await fetcher.fetch("http://127.0.0.1:9000/keys")
    assert result.success is False
    assert result.document is None
    assert result.error is not None
    assert result.error.code == BLOCKED_PRIVATE_ADDRESS
    assert result.error.retryable is False
