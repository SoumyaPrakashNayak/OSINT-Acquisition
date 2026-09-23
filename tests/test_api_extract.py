"""Integration tests for the POST /osint/extract endpoint (Phase 4)."""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def sample_web_document_payload(html: str = "<article><h1>News</h1><p>Body text.</p></article>") -> dict:
    return {
        "web_document": {
            "requested_url": "https://example.com/article",
            "final_url": "https://example.com/article",
            "domain": "example.com",
            "status_code": 200,
            "content_type": "text/html",
            "content_length": len(html.encode("utf-8")),
            "html": html,
            "retrieved_at": "2026-09-22T10:00:00Z",
            "content_hash": "dummy-hash-12345",
        }
    }


@pytest.mark.asyncio
async def test_api_extract_success():
    """Test POST /osint/extract with valid WebDocument returns HTTP 200 and ExtractedDocument."""
    payload = sample_web_document_payload(
        html="""
        <html><head><title>Extracted Headline</title></head>
        <body>
          <article>
            <h1>Heading 1</h1>
            <p>This is a paragraph of meaningful text for the test.</p>
          </article>
        </body></html>
        """
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/extract", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["document"] is not None
        assert data["document"]["title"] == "Extracted Headline"
        assert "meaningful text" in data["document"]["text"]
        assert data["document"]["requested_url"] == "https://example.com/article"
        assert data["error"] is None


@pytest.mark.asyncio
async def test_api_extract_invalid_payload_category_a():
    """Test POST /osint/extract with missing web_document returns HTTP 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/extract", json={})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_api_extract_empty_html_category_b():
    """Test POST /osint/extract on empty HTML returns HTTP 200 with structured EMPTY_HTML error."""
    payload = sample_web_document_payload(html="   ")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/extract", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert data["document"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "EMPTY_HTML"


@pytest.mark.asyncio
async def test_api_extract_unexpected_failure_category_c():
    """Test unexpected internal failure returns HTTP 500 without leaking stack traces."""
    with patch(
        "app.extraction.service.ExtractionService.extract",
        side_effect=RuntimeError("Unexpected unhandled extraction crash"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/osint/extract", json=sample_web_document_payload()
            )
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
            assert "Traceback" not in str(data)
