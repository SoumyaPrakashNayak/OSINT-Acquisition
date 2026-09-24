"""Tests verifying entity extraction determinism across repeated executions (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.service import EntityExtractionService
from app.extraction.models import ContentQuality, ExtractedDocument


def test_entity_extraction_strict_determinism():
    """Verify that multiple consecutive runs on the exact same document yield identical entity outputs."""
    text = (
        "Sundar Pichai visited India on Monday. Later, he joined Google officials in Bhubaneswar. "
        "The conference cost ₹10 lakh and registered attendees via info@example.com or +91 9876543210. "
        "Visit https://example.com for details."
    )
    doc = ExtractedDocument(
        requested_url="https://example.com/article",
        final_url="https://example.com/article",
        domain="example.com",
        content_hash="deterministic-hash-12345",
        retrieved_at=datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc),
        text=text,
        content_quality=ContentQuality.MEDIUM,
    )

    service = EntityExtractionService()

    run1 = service.extract(doc)
    run2 = service.extract(doc)
    run3 = service.extract(doc)

    assert run1.success is True
    assert run2.success is True
    assert run3.success is True

    assert run1.entity_count == run2.entity_count == run3.entity_count
    assert run1.unique_entity_count == run2.unique_entity_count == run3.unique_entity_count
    assert run1.counts_by_type == run2.counts_by_type == run3.counts_by_type

    # Verify every extracted entity field is identical
    for e1, e2, e3 in zip(run1.entities, run2.entities, run3.entities):
        assert e1.id == e2.id == e3.id
        assert e1.type == e2.type == e3.type
        assert e1.text == e2.text == e3.text
        assert e1.normalized_text == e2.normalized_text == e3.normalized_text
        assert e1.start_offset == e2.start_offset == e3.start_offset
        assert e1.end_offset == e2.end_offset == e3.end_offset
        assert e1.sentence == e2.sentence == e3.sentence
        assert e1.confidence == e2.confidence == e3.confidence
        assert e1.source_document_hash == e2.source_document_hash == e3.source_document_hash
