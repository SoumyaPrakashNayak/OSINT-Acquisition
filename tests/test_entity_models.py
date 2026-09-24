"""Tests for entity taxonomy, occurrences, entities, and result models (Phase 5)."""

from datetime import datetime, timezone
import pytest
from app.entity_extraction.models import (
    EntityExtractionError,
    EntityExtractionMetrics,
    EntityExtractionRequest,
    EntityExtractionResult,
    EntityOccurrence,
    ExtractedEntity,
    UniqueEntity,
)
from app.entity_extraction.taxonomy import (
    ENTITY_TYPE_DESCRIPTIONS,
    EntityType,
    is_valid_entity_type,
)
from app.extraction.models import ContentQuality, ExtractedDocument


def make_sample_doc(text: str = "Sundar Pichai visited India.") -> ExtractedDocument:
    return ExtractedDocument(
        requested_url="https://example.com/news",
        final_url="https://example.com/news",
        domain="example.com",
        content_hash="test-hash-12345",
        retrieved_at=datetime.now(timezone.utc),
        title="Test Article",
        text=text,
        content_quality=ContentQuality.MEDIUM,
    )


def test_entity_taxonomy_types_and_validation():
    """Verify minimum required entity taxonomy types are defined and valid."""
    required_types = [
        "PERSON", "ORGANIZATION", "LOCATION", "DATE",
        "TIME", "MONEY", "PHONE", "EMAIL", "URL"
    ]
    for r_type in required_types:
        assert is_valid_entity_type(r_type)
        assert EntityType(r_type) in ENTITY_TYPE_DESCRIPTIONS

    assert not is_valid_entity_type("NOT_AN_ENTITY_TYPE")


def test_extracted_entity_model_instantiation():
    """Verify ExtractedEntity holds offsets, sentence, provenance, and normalized text."""
    ent = ExtractedEntity(
        id="entity-1",
        type=EntityType.PERSON,
        text="Sundar Pichai",
        normalized_text="Sundar Pichai",
        start_offset=0,
        end_offset=13,
        sentence="Sundar Pichai visited India.",
        confidence=0.97,
        source_document_hash="hash-abc",
        source_url="https://example.com/news",
    )
    assert ent.id == "entity-1"
    assert ent.type == EntityType.PERSON
    assert ent.text == "Sundar Pichai"
    assert ent.start_offset == 0
    assert ent.end_offset == 13
    assert ent.confidence == 0.97
    assert ent.source_document_hash == "hash-abc"
    assert ent.source_url == "https://example.com/news"


def test_unique_entity_and_occurrence_model():
    """Verify UniqueEntity groups multiple occurrences."""
    occ1 = EntityOccurrence(
        text="Sundar Pichai",
        start_offset=0,
        end_offset=13,
        sentence="Sundar Pichai visited India.",
        confidence=None,
    )
    occ2 = EntityOccurrence(
        text="Sundar Pichai",
        start_offset=80,
        end_offset=93,
        sentence="Sundar Pichai spoke to reporters.",
        confidence=None,
    )
    unique = UniqueEntity(
        type=EntityType.PERSON,
        normalized_text="Sundar Pichai",
        count=2,
        occurrences=[occ1, occ2],
    )
    assert unique.count == 2
    assert len(unique.occurrences) == 2
    assert unique.occurrences[0].start_offset == 0
    assert unique.occurrences[1].start_offset == 80


def test_entity_extraction_result_contract():
    """Verify EntityExtractionResult serializes metrics, counts, and entities correctly."""
    res = EntityExtractionResult(
        success=True,
        document_hash="hash-123",
        source_url="https://example.com",
        entities=[],
        unique_entities=[],
        entity_count=0,
        mention_count=0,
        unique_entity_count=0,
        counts_by_type={"PERSON": 2, "LOCATION": 1},
        warnings=[],
        error=None,
        metrics=EntityExtractionMetrics(
            character_count=100,
            word_count=20,
            mention_count=3,
            unique_entity_count=2,
            duration_ms=1.5,
        ),
    )
    dumped = res.model_dump()
    assert dumped["success"] is True
    assert dumped["counts_by_type"] == {"PERSON": 2, "LOCATION": 1}
    assert dumped["metrics"]["word_count"] == 20


def test_entity_extraction_request_validation():
    """Verify EntityExtractionRequest requires valid ExtractedDocument."""
    doc = make_sample_doc()
    req = EntityExtractionRequest(document=doc)
    assert req.document.content_hash == "test-hash-12345"
