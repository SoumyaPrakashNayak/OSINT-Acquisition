"""Comprehensive tests for entity extraction logic across all taxonomy types (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.extractor import DeterministicEntityExtractor
from app.entity_extraction.mock_extractor import MockEntityExtractor
from app.entity_extraction.models import ExtractedEntity
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


def test_basic_person_and_location_extraction():
    """Test: 'John Doe visited Mumbai.' -> PERSON = John Doe, LOCATION = Mumbai."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("John Doe visited Mumbai.")
    entities = extractor.extract(doc)

    extracted_types = {e.type for e in entities}
    assert EntityType.PERSON in extracted_types
    assert EntityType.LOCATION in extracted_types

    person = next(e for e in entities if e.type == EntityType.PERSON)
    location = next(e for e in entities if e.type == EntityType.LOCATION)

    assert person.text == "John Doe"
    assert location.text == "Mumbai"


def test_multiple_entities_extraction():
    """Test: 'John Doe joined Google in Mumbai on Monday.' -> PERSON, ORG, LOC, DATE."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("John Doe joined Google in Mumbai on Monday.")
    entities = extractor.extract(doc)

    types = {e.type for e in entities}
    assert EntityType.PERSON in types
    assert EntityType.ORGANIZATION in types
    assert EntityType.LOCATION in types
    assert EntityType.DATE in types

    texts = {e.text for e in entities}
    assert "John Doe" in texts
    assert "Google" in texts
    assert "Mumbai" in texts
    assert "Monday" in texts


def test_organization_extraction():
    """Test organization extraction for global and Indian institutions."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("Google announced a new project with Microsoft and Siksha 'O' Anusandhan.")
    entities = extractor.extract(doc)

    org_entities = [e for e in entities if e.type == EntityType.ORGANIZATION]
    org_texts = {e.text.lower() for e in org_entities}

    assert "google" in org_texts
    assert "microsoft" in org_texts
    assert "siksha 'o' anusandhan" in org_texts


def test_organization_structural_suffix():
    """Test organization names detected via corporate/institutional suffixes."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("Odisha Police arrested the suspect near Acme Corporation.")
    entities = extractor.extract(doc)

    orgs = [e.text for e in entities if e.type == EntityType.ORGANIZATION]
    assert any("Odisha Police" in o for o in orgs)
    assert any("Acme Corporation" in o for o in orgs)


def test_location_extraction():
    """Test: 'The meeting was held in Bhubaneswar, Odisha, India.'"""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("The meeting was held in Bhubaneswar, Odisha, India.")
    entities = extractor.extract(doc)

    locs = [e.text for e in entities if e.type == EntityType.LOCATION]
    assert "Bhubaneswar" in locs
    assert "Odisha" in locs
    assert "India" in locs


def test_date_extraction_formats():
    """Test multiple date formats: named, slash, ISO, and weekday."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc(
        "Events took place on September 21, 2026, then 21/09/2026, followed by 2026-09-22 on Monday."
    )
    entities = extractor.extract(doc)

    dates = [e for e in entities if e.type == EntityType.DATE]
    date_texts = [d.text for d in dates]
    assert any("September 21, 2026" in t for t in date_texts)
    assert any("21/09/2026" in t for t in date_texts)
    assert any("2026-09-22" in t for t in date_texts)
    assert any("Monday" in t for t in date_texts)


def test_time_extraction():
    """Test explicit time extractions: 10:30 AM and 10:30:00."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("The hearing commenced at 10:30 AM and concluded at 4:00 PM (16:00:00).")
    entities = extractor.extract(doc)

    times = [e for e in entities if e.type == EntityType.TIME]
    time_texts = [t.text for t in times]
    assert any("10:30 AM" in t for t in time_texts)
    assert any("4:00 PM" in t for t in time_texts)


def test_money_extraction():
    """Test extraction of monetary amounts in multiple currency formats."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc(
        "The project cost ₹10 lakh, while foreign investments reached $5 million and Rs. 50,000 or INR 25,000."
    )
    entities = extractor.extract(doc)

    moneys = [e.text for e in entities if e.type == EntityType.MONEY]
    assert any("₹10 lakh" in m for m in moneys)
    assert any("$5 million" in m for m in moneys)
    assert any("Rs. 50,000" in m for m in moneys)
    assert any("INR 25,000" in m for m in moneys)


def test_phone_extraction():
    """Test Indian telephone and mobile formats."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc(
        "Contact the hotline at +91 9876543210, +91-98765-43210, or alternate 9876543210."
    )
    entities = extractor.extract(doc)

    phones = [e.text for e in entities if e.type == EntityType.PHONE]
    assert any("9876543210" in p for p in phones)


def test_email_extraction():
    """Test valid email extractions."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("Direct all inquiries to investigation@example.com or support@police.gov.in.")
    entities = extractor.extract(doc)

    emails = [e.text for e in entities if e.type == EntityType.EMAIL]
    assert "investigation@example.com" in emails
    assert "support@police.gov.in" in emails


def test_url_extraction():
    """Test URLs appearing directly inside document body text."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("Visit https://example.com/details for full reports or browse http://data.org/view.")
    entities = extractor.extract(doc)

    urls = [e.text for e in entities if e.type == EntityType.URL]
    assert "https://example.com/details" in urls
    assert "http://data.org/view" in urls


def test_no_coreference_resolution():
    """Test that pronouns like 'He' are NOT resolved or coreferenced to John Doe."""
    extractor = DeterministicEntityExtractor()
    doc = make_doc("John Doe arrived. He spoke to reporters.")
    entities = extractor.extract(doc)

    person_entities = [e for e in entities if e.type == EntityType.PERSON]
    assert len(person_entities) == 1
    assert person_entities[0].text == "John Doe"

    # Ensure no entity was created for pronoun "He" or coreferenced
    all_texts = [e.text for e in entities]
    assert "He" not in all_texts


def test_mock_extractor_deterministic_override():
    """Test MockEntityExtractor allows injecting explicit entities with confidence."""
    mock_entity = ExtractedEntity(
        id="mock-1",
        type=EntityType.PERSON,
        text="Target Individual",
        normalized_text="Target Individual",
        start_offset=0,
        end_offset=17,
        sentence="Target Individual observed at scene.",
        confidence=0.98,
        source_document_hash="dummy",
        source_url="dummy",
    )
    mock_extractor = MockEntityExtractor(default_entities=[mock_entity])
    doc = make_doc("Arbitrary unparsed text.")
    entities = mock_extractor.extract(doc)

    assert len(entities) == 1
    assert entities[0].text == "Target Individual"
    assert entities[0].confidence == 0.98
    assert entities[0].source_document_hash == "sha256-dummy-hash"
