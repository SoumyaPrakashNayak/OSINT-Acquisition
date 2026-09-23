"""Tests for deterministic metadata extraction (Phase 4.2)."""

import pytest
from bs4 import BeautifulSoup
from app.extraction.metadata import (
    extract_author,
    extract_canonical_url,
    extract_dates,
    extract_description,
    extract_language,
    extract_title,
)
from app.extraction.parser import parse_html_safe


def test_title_priority_order():
    """Test title extraction priority: <title> > og:title > twitter:title > <h1>."""
    # 1. <title> present
    html1 = """
    <html><head>
      <title>  Primary Document   Title </title>
      <meta property="og:title" content="OG Title">
      <meta name="twitter:title" content="Twitter Title">
    </head><body><h1>H1 Title</h1></body></html>
    """
    assert extract_title(parse_html_safe(html1)) == "Primary Document Title"

    # 2. No <title>, og:title present
    html2 = """
    <html><head>
      <meta property="og:title" content="  OG   Title ">
      <meta name="twitter:title" content="Twitter Title">
    </head><body><h1>H1 Title</h1></body></html>
    """
    assert extract_title(parse_html_safe(html2)) == "OG Title"

    # 3. No <title> or og:title, twitter:title present
    html3 = """
    <html><head>
      <meta name="twitter:title" content="Twitter   Headline">
    </head><body><h1>H1 Title</h1></body></html>
    """
    assert extract_title(parse_html_safe(html3)) == "Twitter Headline"

    # 4. Fallback to <h1>
    html4 = "<html><body><h1>  Headline From H1  </h1></body></html>"
    assert extract_title(parse_html_safe(html4)) == "Headline From H1"

    # 5. Missing all
    html5 = "<html><body><p>No title anywhere</p></body></html>"
    assert extract_title(parse_html_safe(html5)) is None


def test_description_priority_order():
    """Test description priority: meta description > og:description > twitter:description."""
    # 1. meta description
    html1 = """
    <html><head>
      <meta name="description" content="Meta   summary text">
      <meta property="og:description" content="OG summary">
    </head></html>
    """
    assert extract_description(parse_html_safe(html1)) == "Meta summary text"

    # 2. og:description
    html2 = """
    <html><head>
      <meta property="og:description" content="OG   summary text">
      <meta name="twitter:description" content="Twitter summary">
    </head></html>
    """
    assert extract_description(parse_html_safe(html2)) == "OG summary text"

    # 3. twitter:description
    html3 = '<html><head><meta name="twitter:description" content="Twitter   summary"></head></html>'
    assert extract_description(parse_html_safe(html3)) == "Twitter summary"

    # 4. None
    assert extract_description(parse_html_safe("<html></html>")) is None


def test_canonical_url_resolution():
    """Test canonical URL extraction and relative link resolution."""
    base_url = "https://news.example.com/reports/today"

    # Relative canonical
    html_rel = '<html><head><link rel="canonical" href="/archive/2026-report"></head></html>'
    assert extract_canonical_url(parse_html_safe(html_rel), base_url) == "https://news.example.com/archive/2026-report"

    # Absolute canonical
    html_abs = '<html><head><link rel="canonical" href="https://canonical.example.org/item"></head></html>'
    assert extract_canonical_url(parse_html_safe(html_abs), base_url) == "https://canonical.example.org/item"

    # Missing canonical
    assert extract_canonical_url(parse_html_safe("<html></html>"), base_url) is None


def test_author_extraction_and_byline_normalization():
    """Test author extraction with 'By ' prefix normalization."""
    # 1. meta author
    html_meta = '<html><head><meta name="author" content="By John Doe"></head></html>'
    assert extract_author(parse_html_safe(html_meta)) == "John Doe"

    # 2. article:author
    html_art = '<html><head><meta property="article:author" content="by   Jane   Smith "></head></html>'
    assert extract_author(parse_html_safe(html_art)) == "Jane Smith"

    # 3. Byline class
    html_class = '<html><body><span class="byline">By Ramesh Kumar</span></body></html>'
    assert extract_author(parse_html_safe(html_class)) == "Ramesh Kumar"

    # 4. JSON-LD author
    html_jsonld = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "author": {"@type": "Person", "name": "Special Correspondent"}
      }
      </script>
    </head></html>
    """
    assert extract_author(parse_html_safe(html_jsonld)) == "Special Correspondent"

    # 5. Missing
    assert extract_author(parse_html_safe("<html><body>No author</body></html>")) is None


def test_publication_and_modified_date_extraction():
    """Test extracting and formatting publication and modified dates to ISO-8601."""
    html_meta = """
    <html><head>
      <meta property="article:published_time" content="2026-09-21T10:30:00Z">
      <meta property="article:modified_time" content="2026-09-22T08:00:00Z">
    </head></html>
    """
    pub, mod = extract_dates(parse_html_safe(html_meta))
    assert pub == "2026-09-21T10:30:00+00:00"
    assert mod == "2026-09-22T08:00:00+00:00"

    # Test time datetime tag
    html_time = '<html><body><time datetime="2026-08-15">August 15, 2026</time></body></html>'
    pub2, _ = extract_dates(parse_html_safe(html_time))
    assert "2026-08-15" in pub2

    # Test JSON-LD dates
    html_jsonld = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Article",
        "datePublished": "2026-07-04T12:00:00Z",
        "dateModified": "2026-07-05T14:30:00Z"
      }
      </script>
    </head></html>
    """
    pub3, mod3 = extract_dates(parse_html_safe(html_jsonld))
    assert "2026-07-04" in pub3
    assert "2026-07-05" in mod3

    # Test unparseable date does not crash and returns None
    html_bad_date = '<html><head><meta name="date" content="not-a-valid-date-string"></head></html>'
    pub_bad, mod_bad = extract_dates(parse_html_safe(html_bad_date))
    assert pub_bad is None
    assert mod_bad is None


def test_language_extraction():
    """Test document language extraction from html tag or meta headers."""
    html_tag = '<html lang="en-US"><body>Content</body></html>'
    assert extract_language(parse_html_safe(html_tag)) == "en-US"

    html_meta = '<html><head><meta http-equiv="content-language" content="hi"></head></html>'
    assert extract_language(parse_html_safe(html_meta)) == "hi"

    html_none = "<html><body>Content</body></html>"
    assert extract_language(parse_html_safe(html_none)) is None
