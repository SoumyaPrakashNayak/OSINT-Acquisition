"""Tests verifying extraction determinism across repeated executions (Phase 4)."""

from datetime import datetime, timezone
import pytest
from app.acquisition.models import WebDocument
from app.extraction.extractor import DeterministicHtmlExtractor


def test_extraction_determinism():
    """Verify that extracting the same WebDocument twice produces identical ExtractedDocument objects."""
    extractor = DeterministicHtmlExtractor()

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <title>Deterministic Document</title>
      <meta name="description" content="Consistent extraction description">
      <meta name="author" content="By Reporter">
    </head>
    <body>
      <article>
        <h1>Main Investigation Title</h1>
        <p>First paragraph with deterministic text contents.</p>
        <p>Second paragraph with <a href="/related">Related Reference</a> link.</p>
      </article>
    </body>
    </html>
    """
    web_doc = WebDocument(
        requested_url="https://example.com/item",
        final_url="https://example.com/item",
        domain="example.com",
        status_code=200,
        content_type="text/html",
        content_length=len(html.encode("utf-8")),
        html=html,
        retrieved_at=datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
        content_hash="deterministic-sha256-hash",
    )

    run_1 = extractor.extract(web_doc)
    run_2 = extractor.extract(web_doc)

    assert run_1.model_dump() == run_2.model_dump()
