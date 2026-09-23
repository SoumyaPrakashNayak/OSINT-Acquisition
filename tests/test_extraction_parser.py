"""Tests for HTML parsing, non-content decomposition, boilerplate stripping, and headings (Phase 4.1)."""

import pytest
from app.extraction.parser import (
    clean_dom_tree,
    extract_headings,
    parse_html_safe,
)


def test_simple_valid_html_parsing():
    """Test parsing standard well-formed HTML."""
    html = "<html><head><title>Test Title</title></head><body><p>Hello world</p></body></html>"
    soup = parse_html_safe(html)
    assert soup.find("title").get_text() == "Test Title"
    assert soup.find("p").get_text() == "Hello world"


def test_malformed_html_graceful_handling():
    """Test malformed HTML with unclosed tags and missing root elements does not crash."""
    malformed = "<div><p>Paragraph without close tag <h1>Heading<b>bold text"
    soup = parse_html_safe(malformed)
    assert soup is not None
    assert "Paragraph without close tag" in soup.get_text()


def test_non_content_tags_removed():
    """Test script, style, noscript, svg, and canvas elements are purged from DOM."""
    html = """
    <html>
      <head>
        <style>body { color: red; }</style>
      </head>
      <body>
        <script>alert('malicious');</script>
        <noscript>Please enable javascript</noscript>
        <svg><circle cx="50" cy="50" r="40" /></svg>
        <p>Legitimate article text.</p>
      </body>
    </html>
    """
    soup = parse_html_safe(html)
    clean_dom_tree(soup)

    assert soup.find("script") is None
    assert soup.find("style") is None
    assert soup.find("noscript") is None
    assert soup.find("svg") is None
    assert "alert" not in soup.get_text()
    assert "Legitimate article text." in soup.get_text()


def test_boilerplate_structures_removed():
    """Test nav, footer, aside, ads, and cookie banners are stripped while article content remains."""
    html = """
    <html>
      <body>
        <nav class="navbar"><a href="/">Home</a><a href="/about">About</a></nav>
        <div class="cookie-banner"><p>We use cookies</p></div>
        <div class="ad-container"><p>Buy something!</p></div>
        <article>
          <h1>Actual News Title</h1>
          <p>This is the core investigative reporting content that must be preserved.</p>
        </article>
        <aside class="sidebar"><p>Related stories widget</p></aside>
        <footer class="site-footer"><p>Copyright 2026</p></footer>
      </body>
    </html>
    """
    soup = parse_html_safe(html)
    clean_dom_tree(soup)

    text = soup.get_text()
    assert "Actual News Title" in text
    assert "core investigative reporting content" in text
    assert "Home" not in text
    assert "We use cookies" not in text
    assert "Buy something!" not in text
    assert "Related stories widget" not in text
    assert "Copyright 2026" not in text


def test_heading_extraction_order_and_levels():
    """Test headings h1-h6 are extracted in document order with levels and whitespace cleaned."""
    html = """
    <html>
      <body>
        <h1>  First   Major Heading  </h1>
        <p>Intro text</p>
        <h2>Sub-section   1</h2>
        <h3> Detail 1.1 </h3>
        <h1>Second Major Heading</h1>
        <h6>Minor Footnote Heading</h6>
        <h2>   </h2> <!-- Empty heading should be ignored -->
      </body>
    </html>
    """
    soup = parse_html_safe(html)
    headings = extract_headings(soup)

    assert len(headings) == 5
    assert headings[0].level == 1
    assert headings[0].text == "First Major Heading"
    assert headings[1].level == 2
    assert headings[1].text == "Sub-section 1"
    assert headings[2].level == 3
    assert headings[2].text == "Detail 1.1"
    assert headings[3].level == 1
    assert headings[3].text == "Second Major Heading"
    assert headings[4].level == 6
    assert headings[4].text == "Minor Footnote Heading"
