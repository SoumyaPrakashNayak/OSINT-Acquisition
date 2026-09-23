"""Tests for main content extraction, paragraph separation, and provenance preservation (Phase 4.3)."""

from datetime import datetime, timezone
import pytest
from app.acquisition.models import WebDocument
from app.extraction.extractor import DeterministicHtmlExtractor


@pytest.fixture
def extractor() -> DeterministicHtmlExtractor:
    return DeterministicHtmlExtractor()


def create_sample_web_document(html: str) -> WebDocument:
    return WebDocument(
        requested_url="https://example.com/initial",
        final_url="https://example.com/article-123",
        domain="example.com",
        status_code=200,
        content_type="text/html",
        content_length=len(html.encode("utf-8")),
        html=html,
        retrieved_at=datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc),
        content_hash="sha256-sample-hash-12345",
    )


def test_article_container_detection(extractor: DeterministicHtmlExtractor):
    """Test <article> tag is detected as primary content container."""
    html = """
    <html><body>
      <div class="sidebar">Sidebar noise</div>
      <article>
        <h1>Article Headline</h1>
        <p>This is the first paragraph of the main reporting story.</p>
        <p>This is the second paragraph providing more context.</p>
      </article>
      <footer>Footer noise</footer>
    </body></html>
    """
    web_doc = create_sample_web_document(html)
    extracted = extractor.extract(web_doc)

    assert extracted.extraction_method == "deterministic_html_article"
    assert len(extracted.paragraphs) == 2
    assert "first paragraph" in extracted.paragraphs[0]
    assert "second paragraph" in extracted.paragraphs[1]
    assert "\n\n" in extracted.text
    assert "Sidebar noise" not in extracted.text


def test_main_tag_detection(extractor: DeterministicHtmlExtractor):
    """Test <main> tag is detected when <article> is absent."""
    html = """
    <html><body>
      <main>
        <h1>Main Topic</h1>
        <p>Reporting within the main semantic element.</p>
      </main>
    </body></html>
    """
    web_doc = create_sample_web_document(html)
    extracted = extractor.extract(web_doc)

    assert extracted.extraction_method == "deterministic_html_main"
    assert "Reporting within the main semantic element." in extracted.text


def test_class_based_container_detection(extractor: DeterministicHtmlExtractor):
    """Test div with article-body class is detected when semantic tags are absent."""
    html = """
    <html><body>
      <div class="header">Header</div>
      <div class="article-body">
        <p>Class-targeted article body text with sufficient length for recognition.</p>
      </div>
    </body></html>
    """
    web_doc = create_sample_web_document(html)
    extracted = extractor.extract(web_doc)

    assert extracted.extraction_method == "deterministic_html_container"
    assert "Class-targeted article body text" in extracted.text


def test_body_fallback_detection(extractor: DeterministicHtmlExtractor):
    """Test fallback to body when no article or semantic container is identifiable."""
    html = """
    <html><body>
      <p>A simple page with no specific article wrapper containers.</p>
    </body></html>
    """
    web_doc = create_sample_web_document(html)
    extracted = extractor.extract(web_doc)

    assert extracted.extraction_method == "deterministic_html_body_fallback"
    assert "simple page with no specific article wrapper" in extracted.text
    assert any("fell back to body" in w for w in extracted.warnings)


def test_raw_html_immutability(extractor: DeterministicHtmlExtractor):
    """Verify that the WebDocument.html is not mutated or modified by extraction."""
    raw_markup = "<html><body><article><p>Unchanged original raw content.</p></article></body></html>"
    web_doc = create_sample_web_document(raw_markup)

    extracted = extractor.extract(web_doc)
    # The source WebDocument html must be strictly untouched
    assert web_doc.html == raw_markup
    assert "<article>" in web_doc.html
    # Extracted text is cleaned
    assert extracted.text == "Unchanged original raw content."


def test_provenance_preservation(extractor: DeterministicHtmlExtractor):
    """Verify all provenance fields are accurately carried over from WebDocument."""
    web_doc = create_sample_web_document("<p>Some body text for extraction.</p>")
    extracted = extractor.extract(web_doc)

    assert extracted.requested_url == web_doc.requested_url
    assert extracted.final_url == web_doc.final_url
    assert extracted.domain == web_doc.domain
    assert extracted.content_hash == web_doc.content_hash
    assert extracted.retrieved_at == web_doc.retrieved_at
