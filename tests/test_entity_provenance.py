"""Tests verifying entity extraction provenance tracking (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.service import EntityExtractionService
from app.extraction.models import ContentQuality, ExtractedDocument


def test_entity_provenance_preservation():
    """Verify that every extracted entity retains source_document_hash and source_url."""
    test_hash = "abc123def4567890abcdef1234567890abcdef12"
    test_url = "https://example.com/investigative-report-2026"

    doc = ExtractedDocument(
        requested_url="https://example.com/initial",
        final_url=test_url,
        domain="example.com",
        content_hash=test_hash,
        retrieved_at=datetime.now(timezone.utc),
        text="Ramesh Kumar visited Odisha Police headquarters in Bhubaneswar on 2026-09-24.",
        content_quality=ContentQuality.HIGH,
    )

    service = EntityExtractionService()
    result = service.extract(doc)

    assert result.success is True
    assert result.document_hash == test_hash
    assert result.source_url == test_url
    assert len(result.entities) > 0

    for ent in result.entities:
        assert ent.source_document_hash == test_hash
        assert ent.source_url == test_url
