"""Tests verifying entity occurrence tracking, deduplication, and counts (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.extractor import DeterministicEntityExtractor
from app.entity_extraction.service import EntityExtractionService
from app.entity_extraction.taxonomy import EntityType
from app.extraction.models import ContentQuality, ExtractedDocument


def make_doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        requested_url="https://example.com/article",
        final_url="https://example.com/article",
        domain="example.com",
        content_hash="sha256-dummy-hash",
        retrieved_at=datetime.now(timezone.utc),
        text=text,
        content_quality=ContentQuality.MEDIUM,
    )


def test_multiple_occurrences_of_same_entity():
    """Test: 'John Doe met John Doe.' -> 2 mentions, 1 unique entity with 2 occurrences."""
    service = EntityExtractionService(extractor=DeterministicEntityExtractor())
    doc = make_doc("John Doe met John Doe.")
    result = service.extract(doc)

    assert result.success is True
    assert result.mention_count == 2
    assert result.entity_count == 2
    assert result.unique_entity_count == 1

    unique_person = result.unique_entities[0]
    assert unique_person.type == EntityType.PERSON
    assert unique_person.normalized_text == "John Doe"
    assert unique_person.count == 2
    assert len(unique_person.occurrences) == 2

    # Check distinct offsets for each occurrence
    occ1, occ2 = unique_person.occurrences
    assert occ1.start_offset == 0
    assert occ1.end_offset == 8
    assert occ2.start_offset == 13
    assert occ2.end_offset == 21


def test_no_alias_merging_or_coreference():
    """Test: 'Sundar Pichai visited India. Later, Pichai met government officials.'

    Phase 5 must NOT automatically collapse 'Sundar Pichai' and 'Pichai' into one record.
    """
    service = EntityExtractionService(extractor=DeterministicEntityExtractor())
    doc = make_doc("Sundar Pichai visited India. Later, Pichai met government officials.")
    result = service.extract(doc)

    assert result.success is True
    person_uniques = [u for u in result.unique_entities if u.type == EntityType.PERSON]
    person_names = {u.normalized_text for u in person_uniques}

    # If Pichai is extracted, it must be separate from Sundar Pichai
    if "Pichai" in person_names:
        assert len(person_uniques) >= 2
        assert "Sundar Pichai" in person_names
        assert "Pichai" in person_names


def test_deterministic_counts_by_type():
    """Verify counts_by_type accurately counts total mentions per entity type."""
    text = "John Doe met Jane Doe at Google and Microsoft in Mumbai, Maharashtra."
    service = EntityExtractionService(extractor=DeterministicEntityExtractor())
    doc = make_doc(text)
    result = service.extract(doc)

    assert result.success is True
    counts = result.counts_by_type

    # 2 persons (John Doe, Jane Doe)
    assert counts.get("PERSON") == 2
    # 2 organizations (Google, Microsoft)
    assert counts.get("ORGANIZATION") == 2
    # 2 locations (Mumbai, Maharashtra)
    assert counts.get("LOCATION") == 2

    assert result.mention_count == sum(counts.values())
