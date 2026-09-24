"""Security tests verifying passive, inert entity extraction on untrusted data (Phase 5)."""

from datetime import datetime, timezone
from unittest.mock import patch
from app.entity_extraction.service import EntityExtractionService
from app.extraction.models import ContentQuality, ExtractedDocument


def test_entity_extraction_makes_zero_network_calls():
    """Verify that entity extraction performs zero outbound network requests."""
    doc = ExtractedDocument(
        requested_url="https://example.com/article",
        final_url="https://example.com/article",
        domain="example.com",
        content_hash="sec-test-hash",
        retrieved_at=datetime.now(timezone.utc),
        text=(
            "Sundar Pichai visited Mumbai. Contact https://malicious.example.com/track "
            "or email attacker@exploit.net or phone +91 9876543210."
        ),
        content_quality=ContentQuality.MEDIUM,
    )

    service = EntityExtractionService()

    with patch("httpx.AsyncClient.get") as mock_http_get, patch(
        "httpx.AsyncClient.post"
    ) as mock_http_post, patch("urllib.request.urlopen") as mock_urllib, patch(
        "socket.socket"
    ) as mock_socket:
        result = service.extract(doc)

        assert not mock_http_get.called
        assert not mock_http_post.called
        assert not mock_urllib.called
        assert not mock_socket.called
        assert result.success is True


def test_entity_extraction_inert_against_code_injection():
    """Verify that hostile code and injection strings in document text are treated strictly as inert data."""
    malicious_text = (
        "<script>alert(document.cookie);</script>\n"
        "'; DROP TABLE entities; --\n"
        "$(rm -rf /)\n"
        "{{7*7}}\n"
        "Ramesh Kumar visited Odisha Police headquarters."
    )

    doc = ExtractedDocument(
        requested_url="https://example.com/article",
        final_url="https://example.com/article",
        domain="example.com",
        content_hash="inject-hash",
        retrieved_at=datetime.now(timezone.utc),
        text=malicious_text,
        content_quality=ContentQuality.HIGH,
    )

    service = EntityExtractionService()
    result = service.extract(doc)

    assert result.success is True
    # The valid person and organization mentions are cleanly extracted
    person_texts = [e.text for e in result.entities]
    assert "Ramesh Kumar" in person_texts
