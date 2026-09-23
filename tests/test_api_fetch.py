"""Tests for Phase 3 API endpoints (/osint/fetch and /osint/fetch-batch)."""

from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import get_web_fetcher
from app.acquisition.mock_fetcher import MockWebFetcher
from app.main import app


@pytest.fixture
def mock_fetcher():
    fetcher = MockWebFetcher()
    fetcher.add_response("https://example.com/article", html="<html><body>Article</body></html>")
    fetcher.add_response("https://example.com/missing", status_code=404)
    return fetcher


@pytest.mark.asyncio
async def test_api_fetch_success(mock_fetcher):
    """Test 3.7.1: POST /osint/fetch with valid accessible URL returns 200 and document."""
    app.dependency_overrides[get_web_fetcher] = lambda: mock_fetcher

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/osint/fetch", json={"url": "https://example.com/article"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["document"] is not None
        assert data["document"]["requested_url"] == "https://example.com/article"
        assert data["document"]["html"] == "<html><body>Article</body></html>"
        assert data["error"] is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_fetch_invalid_url_category_a():
    """Test 3.7.2: Category A invalid request returns HTTP 422 validation response."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Malformed scheme
        response = await client.post(
            "/osint/fetch", json={"url": "ftp://example.com/doc"}
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] in ("INVALID_REQUEST", "INVALID_TARGET")

        # Empty URL
        response_empty = await client.post("/osint/fetch", json={"url": ""})
        assert response_empty.status_code == 422


@pytest.mark.asyncio
async def test_api_fetch_controlled_failure_category_b(mock_fetcher):
    """Test 3.7.3: Category B controlled acquisition failure (404) returns HTTP 200 with structured error."""
    app.dependency_overrides[get_web_fetcher] = lambda: mock_fetcher

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/osint/fetch", json={"url": "https://example.com/missing"}
        )
        # MUST return HTTP 200, not HTTP 500 or 404
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["document"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "HTTP_NOT_FOUND"
        assert data["error"]["retryable"] is False
        assert data["metadata"]["status_code"] == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_fetch_batch(mock_fetcher):
    """Test 3.7.4: POST /osint/fetch-batch returns aggregated batch results."""
    app.dependency_overrides[get_web_fetcher] = lambda: mock_fetcher

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        payload = {
            "urls": [
                "https://example.com/article",
                "https://example.com/missing",
            ]
        }
        response = await client.post("/osint/fetch-batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert len(data["results"]) == 2

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_unexpected_failure_category_c():
    """Test 3.7.5: Category C unexpected internal bug returns HTTP 500 without stack trace leak."""
    with patch(
        "app.acquisition.service.AcquisitionService.acquire",
        side_effect=RuntimeError("Unexpected unhandled memory corruption"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/osint/fetch", json={"url": "https://example.com/article"}
            )
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
            # Ensure raw exception text/traceback is NOT leaked to API client
            assert "memory corruption" not in data["error"]["message"]
            assert "Traceback" not in str(data)
