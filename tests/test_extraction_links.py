"""Tests for hyperlink extraction, resolution, filtering, and deduplication (Phase 4)."""

import pytest
from app.extraction.parser import extract_links, parse_html_safe


def test_link_extraction_and_resolution():
    """Test extracting links, resolving relative URLs against base URL, and ignoring non-http links."""
    base_url = "https://news.example.com/reports/investigation"
    html = """
    <div>
      <a href="https://court.gov.in/case/123">Supreme Court Ruling</a>
      <a href="/archive/2026/brief">Archive Brief</a>
      <a href="#section-top">Jump to Top</a>
      <a href="mailto:tips@example.com">Send Tips</a>
      <a href="javascript:void(0)">Click Here</a>
    </div>
    """
    soup = parse_html_safe(html)
    links = extract_links(soup, base_url, max_links=10)

    assert len(links) == 2
    assert links[0].text == "Supreme Court Ruling"
    assert links[0].url == "https://court.gov.in/case/123"
    assert links[1].text == "Archive Brief"
    assert links[1].url == "https://news.example.com/archive/2026/brief"


def test_link_deduplication_preserves_order():
    """Test exact duplicate URLs are collapsed while maintaining first-seen order."""
    base_url = "https://example.com"
    html = """
    <div>
      <a href="https://partner.example.org/press">First Press Link</a>
      <a href="https://partner.example.org/press">Duplicate Press Link</a>
      <a href="https://other.example.org/page">Second Unique Link</a>
    </div>
    """
    soup = parse_html_safe(html)
    links = extract_links(soup, base_url, max_links=10)

    assert len(links) == 2
    assert links[0].url == "https://partner.example.org/press"
    assert links[0].text == "First Press Link"
    assert links[1].url == "https://other.example.org/page"


def test_max_links_limit_respected():
    """Test maximum links parameter caps the total number of extracted links."""
    base_url = "https://example.com"
    links_html = "".join(f'<a href="https://link{i}.example.com">Link {i}</a>' for i in range(20))
    soup = parse_html_safe(f"<div>{links_html}</div>")

    links = extract_links(soup, base_url, max_links=5)
    assert len(links) == 5
