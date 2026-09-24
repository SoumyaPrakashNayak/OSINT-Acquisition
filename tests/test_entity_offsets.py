"""Tests verifying character offsets and sentence context fidelity (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.extractor import (
    DeterministicEntityExtractor,
    split_sentences_with_spans,
)
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


def test_character_offsets_exact_substring_match():
    """Verify that document.text[start_offset:end_offset] == entity.text for all extracted entities."""
    text = (
        "Sundar Pichai visited India on Monday. Later, he joined Google officials in Bhubaneswar. "
        "The conference cost ₹10 lakh and registered attendees via info@example.com or +91 9876543210. "
        "See https://example.com for further updates."
    )
    doc = make_doc(text)
    extractor = DeterministicEntityExtractor()
    entities = extractor.extract(doc)

    assert len(entities) >= 7

    for ent in entities:
        # Crucial offset guarantee: exact substring equality
        slice_text = text[ent.start_offset : ent.end_offset]
        assert slice_text == ent.text, f"Offset mismatch for {ent.type}: '{slice_text}' != '{ent.text}'"
        assert ent.start_offset >= 0
        assert ent.end_offset > ent.start_offset


def test_sentence_context_association():
    """Verify each entity is associated with its exact containing sentence."""
    text = (
        "First sentence mentions Ramesh Kumar in New Delhi.\n"
        "Second sentence mentions Odisha Police in Bhubaneswar.\n"
        "Third sentence mentions 2026-09-24 and ₹10 lakh."
    )
    doc = make_doc(text)
    extractor = DeterministicEntityExtractor()
    entities = extractor.extract(doc)

    for ent in entities:
        assert ent.sentence is not None
        assert ent.text in ent.sentence
        assert ent.sentence in text


def test_split_sentences_with_spans():
    """Verify sentence splitter correctly ignores abbreviations and handles newlines."""
    text = "Dr. Ramesh Kumar met Mr. John Doe in Mumbai. He announced 10.5 percent growth."
    spans = split_sentences_with_spans(text)

    # Should not split at 'Dr.' or 'Mr.' or '10.5'
    assert len(spans) == 2
    sent1 = spans[0][2]
    sent2 = spans[1][2]

    assert "Dr. Ramesh Kumar met Mr. John Doe in Mumbai." in sent1
    assert "He announced 10.5 percent growth." in sent2
