"""Tests verifying extraction remains strictly passive and inert (Phase 4 Security)."""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from app.acquisition.models import WebDocument
from app.extraction.extractor import DeterministicHtmlExtractor


def test_extraction_makes_no_network_requests():
    """Verify that parsing HTML containing remote images, scripts, and links makes zero HTTP requests."""
    extractor = DeterministicHtmlExtractor()

    malicious_or_remote_html = """
    <html>
      <head>
        <link rel="stylesheet" href="http://malicious.example.com/steal.css">
        <script src="http://malicious.example.com/exploit.js"></script>
      </head>
      <body>
        <img src="http://internal-service.local/pingback">
        <article>
          <h1>Clean News Title</h1>
          <p>This is safe inert text being parsed.</p>
        </article>
      </body>
    </html>
    """
    web_doc = WebDocument(
        requested_url="https://example.com/page",
        final_url="https://example.com/page",
        domain="example.com",
        status_code=200,
        content_type="text/html",
        content_length=len(malicious_or_remote_html.encode("utf-8")),
        html=malicious_or_remote_html,
        retrieved_at=datetime.now(timezone.utc),
        content_hash="dummy-hash",
    )

    with patch("httpx.AsyncClient.get") as mock_http_get, patch(
        "urllib.request.urlopen"
    ) as mock_urllib:
        extracted = extractor.extract(web_doc)

        # Ensure no network socket or client method was ever invoked
        assert not mock_http_get.called
        assert not mock_urllib.called

        # Content extracted successfully and cleanly
        assert extracted.title == "Clean News Title"
        assert "This is safe inert text" in extracted.text
