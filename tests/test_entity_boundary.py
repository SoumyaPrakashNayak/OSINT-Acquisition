"""Mandatory test verifying the strict boundary between entity extraction and target resolution (Phase 5)."""

from datetime import datetime, timezone
from app.entity_extraction.service import EntityExtractionService
from app.entity_extraction.taxonomy import EntityType
from app.extraction.models import ContentQuality, ExtractedDocument


def test_target_resolution_boundary_enforcement():
    """Verify that Phase 5 extracts entities without attempting target matching or resolution.

    Requirement:
    Input target: {"name": "Ramesh Kumar"}
    Document: "Ramesh Kumar attended the event. Another person named Ramesh Kumar spoke later."
    Phase 5 must extract the mentions.
    It must NOT output:
    - target_match = true
    - identity_confidence = ...
    - same_person = true
    There must be no target resolution logic.
    """
    # Simulated target under investigation
    target = {"name": "Ramesh Kumar"}

    doc_text = "Ramesh Kumar attended the event. Another person named Ramesh Kumar spoke later."
    doc = ExtractedDocument(
        requested_url="https://example.com/news",
        final_url="https://example.com/news",
        domain="example.com",
        content_hash="boundary-test-hash",
        retrieved_at=datetime.now(timezone.utc),
        text=doc_text,
        content_quality=ContentQuality.MEDIUM,
    )

    service = EntityExtractionService()
    result = service.extract(doc)

    assert result.success is True
    # Mentions are extracted
    person_mentions = [e for e in result.entities if e.type == EntityType.PERSON]
    assert len(person_mentions) == 2
    for p in person_mentions:
        assert p.text == "Ramesh Kumar"

    # Strict check: serialize output to dictionary and verify absence of any target resolution fields
    result_dict = result.model_dump()

    forbidden_fields = [
        "target_match",
        "identity_confidence",
        "same_person",
        "target_person",
        "is_target",
        "target_similarity",
        "suspect_score",
        "risk_score",
        "criminal_association",
    ]

    def assert_no_forbidden_keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in forbidden_fields, f"Forbidden target resolution field '{k}' found in output!"
                assert_no_forbidden_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                assert_no_forbidden_keys(item)

    assert_no_forbidden_keys(result_dict)
