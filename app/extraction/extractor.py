"""Content extractor protocol and deterministic HTML extraction implementation."""

from typing import Protocol, runtime_checkable
from app.acquisition.models import WebDocument
from app.config import settings
from app.extraction.errors import EMPTY_HTML, HTML_PARSE_ERROR, ExtractionException
from app.extraction.metadata import (
    extract_author,
    extract_canonical_url,
    extract_dates,
    extract_description,
    extract_language,
    extract_title,
)
from app.extraction.models import ExtractedDocument
from app.extraction.parser import (
    clean_dom_tree,
    extract_headings,
    extract_links,
    extract_paragraphs_and_text,
    find_main_container,
    parse_html_safe,
)
from app.extraction.quality import calculate_metrics


@runtime_checkable
class ContentExtractor(Protocol):
    """Protocol defining the interface for extracting structured content from a WebDocument."""

    def extract(self, web_document: WebDocument) -> ExtractedDocument:
        """Extract structured textual and metadata representation from WebDocument."""
        ...


class DeterministicHtmlExtractor(ContentExtractor):
    """Deterministic extractor implementing passive HTML parsing, metadata extraction, and boilerplate reduction."""

    def extract(self, web_document: WebDocument) -> ExtractedDocument:
        """Extract structured content from WebDocument.

        Args:
            web_document: Authoritative acquired WebDocument from Phase 3.

        Returns:
            ExtractedDocument: Structured document with metadata, content, and quality metrics.

        Raises:
            ExtractionException: If HTML is empty or completely unparseable.
        """
        raw_html = web_document.html
        if not raw_html or not raw_html.strip():
            raise ExtractionException(
                code=EMPTY_HTML,
                message="Acquired HTML document is empty or blank.",
                retryable=False,
            )

        warnings: list[str] = []

        try:
            soup = parse_html_safe(raw_html)
        except Exception as exc:
            raise ExtractionException(
                code=HTML_PARSE_ERROR,
                message=f"Failed to parse HTML document: {exc}",
                retryable=False,
            )

        # 1. Extract metadata before decomposing any DOM elements
        title = extract_title(soup)
        if not title:
            warnings.append("No title found in document markup.")

        description = extract_description(soup)
        canonical_url = extract_canonical_url(soup, web_document.final_url)
        author = extract_author(soup)
        pub_date, mod_date = extract_dates(soup)
        language = extract_language(soup)

        # Extract headings before decomposing boilerplate
        headings = extract_headings(soup)

        # 2. Decompose script, style, comments, and boilerplate
        clean_dom_tree(soup)

        # 3. Detect primary content container and strategy
        container, strategy = find_main_container(soup)
        if strategy == "deterministic_html_body_fallback":
            warnings.append("No semantic article or main container detected; fell back to body.")

        # 4. Extract paragraphs and formatted readable text
        paragraphs, text = extract_paragraphs_and_text(container)

        # 5. Extract resolved links
        max_links = getattr(settings, "max_extracted_links", 100)
        links = extract_links(container, web_document.final_url, max_links=max_links)

        # 6. Calculate quality metrics and classification
        metrics = calculate_metrics(text, paragraphs, headings, links)

        # 7. Assemble final ExtractedDocument preserving provenance anchors
        extracted_doc = ExtractedDocument(
            # Provenance
            requested_url=web_document.requested_url,
            final_url=web_document.final_url,
            domain=web_document.domain,
            content_hash=web_document.content_hash,
            retrieved_at=web_document.retrieved_at,
            # Metadata
            title=title,
            description=description,
            canonical_url=canonical_url,
            author=author,
            publication_date=pub_date,
            modified_date=mod_date,
            language=language,
            # Content
            headings=headings,
            paragraphs=paragraphs,
            text=text,
            links=links,
            # Metrics
            content_length=metrics["content_length"],
            word_count=metrics["word_count"],
            character_count=metrics["character_count"],
            paragraph_count=metrics["paragraph_count"],
            heading_count=metrics["heading_count"],
            link_count=metrics["link_count"],
            extraction_method=strategy,
            content_quality=metrics["content_quality"],
            warnings=warnings,
        )

        return extracted_doc
