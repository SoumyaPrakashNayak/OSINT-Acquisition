"""Tests for real search provider adapter (HttpSearchProvider)."""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.discovery.http_provider import HttpSearchProvider
from app.models.errors import SearchProviderException, SearchTimeoutException


@pytest.mark.asyncio
async def test_searxng_response_parsing():
    """Test HttpSearchProvider successfully parses SearXNG JSON response."""
    mock_json = {
        "results": [
            {
                "title": "Ramesh Kumar News Article",
                "url": "https://news.odisha.example.com/article1",
                "content": "A report regarding Ramesh Kumar...",
                "engine": "google news",
            }
        ]
    }

    provider = HttpSearchProvider(provider_type="searxng", api_url="http://localhost:8080/search")

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_json
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = await provider.search('"Ramesh Kumar"')
        assert len(results) == 1
        assert results[0].title == "Ramesh Kumar News Article"
        assert results[0].url == "https://news.odisha.example.com/article1"
        assert results[0].source == "google news"


@pytest.mark.asyncio
async def test_serpapi_missing_key_raises_error():
    """Test SerpAPI provider requires an API key before searching."""
    provider = HttpSearchProvider(provider_type="serpapi", api_key=None)
    with pytest.raises(SearchProviderException) as exc_info:
        await provider.search('"Ramesh Kumar"')
    assert "SEARCH_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_provider_timeout_handling():
    """Test network timeout raises SearchTimeoutException gracefully."""
    provider = HttpSearchProvider(provider_type="searxng", timeout=0.1)

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(SearchTimeoutException) as exc_info:
            await provider.search('"Ramesh Kumar"')
        assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_provider_http_error_handling():
    """Test external HTTP error raises SearchProviderException without leaking keys."""
    secret_key = "super-secret-key-123"
    provider = HttpSearchProvider(provider_type="searxng", api_key=secret_key)

    mock_request = httpx.Request("GET", "http://localhost:8080/search")
    mock_response = httpx.Response(502, request=mock_request)

    with patch(
        "httpx.AsyncClient.get",
        side_effect=httpx.HTTPStatusError("Bad Gateway", request=mock_request, response=mock_response),
    ):
        with pytest.raises(SearchProviderException) as exc_info:
            await provider.search('"Ramesh Kumar"')
        # Ensure secret API key is NOT contained in the exception message
        assert secret_key not in str(exc_info.value)
        assert "HTTP 502" in str(exc_info.value)
