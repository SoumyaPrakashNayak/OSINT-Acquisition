"""Integration tests for POST /osint/entities endpoint (Phase 5)."""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.entity_extraction.taxonomy import EntityType
from app.main import app


def sample_extracted_document_payload(text: str = "Sundar Pichai visited India.") -> dict:
    return {
        "document": {
            "requested_url": "https://example.com/article",
            "final_url": "https://example.com/article",
            "domain": "example.com",
            "content_hash": "sha256-test-hash",
            "retrieved_at": "2026-09-24T10:00:00Z",
            "title": "Sample Article",
            "description": "Article summary",
            "canonical_url": "https://example.com/article",
            "author": "Reporter",
            "publication_date": "2026-09-24",
            "modified_date": None,
            "language": "en",
            "headings": [],
            "paragraphs": [text],
            "text": text,
            "links": [],
            "content_length": len(text),
            "word_count": len(text.split()),
            "character_count": len(text),
            "paragraph_count": 1,
            "heading_count": 0,
            "link_count": 0,
            "extraction_method": "deterministic_html",
            "content_quality": "HIGH",
            "warnings": [],
        }
    }


@pytest.mark.asyncio
async def test_api_entities_success():
    """Test POST /osint/entities returns HTTP 200 with extracted entities and metrics."""
    payload = sample_extracted_document_payload(
        text="Sundar Pichai visited India on Monday. Later, he joined Google officials in Bhubaneswar."
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/entities", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["document_hash"] == "sha256-test-hash"
        assert len(data["entities"]) > 0
        assert data["entity_count"] == len(data["entities"])
        assert data["mention_count"] == len(data["entities"])
        assert data["unique_entity_count"] == len(data["unique_entities"])
        assert "counts_by_type" in data
        assert "PERSON" in data["counts_by_type"]
        assert data["error"] is None


@pytest.mark.asyncio
async def test_api_entities_invalid_payload_category_a():
    """Test POST /osint/entities with missing document returns HTTP 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/entities", json={})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
async def test_api_entities_empty_text_category_b():
    """Test POST /osint/entities with empty text returns HTTP 200 with EMPTY_DOCUMENT error."""
    payload = sample_extracted_document_payload(text="   ")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/entities", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert data["entities"] == []
        assert data["error"] is not None
        assert data["error"]["code"] == "EMPTY_DOCUMENT"
        assert data["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_api_entities_unexpected_crash_category_c():
    """Test unexpected internal crash returns HTTP 500 without stack traces."""
    with patch(
        "app.entity_extraction.service.EntityExtractionService.extract",
        side_effect=RuntimeError("Unexpected unhandled NER crash"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/osint/entities", json=sample_extracted_document_payload()
            )
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
            assert "Traceback" not in str(data)
