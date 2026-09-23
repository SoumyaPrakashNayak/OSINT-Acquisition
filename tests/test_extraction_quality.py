"""Tests for content metrics and quality grading (Phase 4)."""

import pytest
from app.extraction.models import ContentQuality, HeadingItem, LinkItem
from app.extraction.quality import calculate_metrics


def test_quality_empty():
    """Test empty text produces ContentQuality.EMPTY."""
    metrics = calculate_metrics("", [], [], [])
    assert metrics["content_quality"] == ContentQuality.EMPTY
    assert metrics["word_count"] == 0
    assert metrics["content_length"] == 0


def test_quality_low():
    """Test text with under 50 words produces ContentQuality.LOW."""
    text = "Short breaking news alert with only a few words of text."
    metrics = calculate_metrics(text, [text], [], [])
    assert metrics["content_quality"] == ContentQuality.LOW
    assert 0 < metrics["word_count"] < 50


def test_quality_medium():
    """Test text between 50 and 199 words produces ContentQuality.MEDIUM."""
    # Generate ~75 words
    words = ["investigation", "target", "evidence", "report", "police"] * 15
    text = " ".join(words)
    metrics = calculate_metrics(text, [text], [], [])
    assert metrics["content_quality"] == ContentQuality.MEDIUM
    assert 50 <= metrics["word_count"] < 200


def test_quality_high():
    """Test substantial text (>= 200 words) produces ContentQuality.HIGH."""
    words = ["investigation", "target", "evidence", "report", "police", "court", "record", "witness"] * 30
    text = " ".join(words)
    metrics = calculate_metrics(text, [text], [], [])
    assert metrics["content_quality"] == ContentQuality.HIGH
    assert metrics["word_count"] >= 200


def test_metrics_counts():
    """Test accurate computation of paragraph, heading, and link counts."""
    text = "Word word word."
    paragraphs = ["P1", "P2", "P3"]
    headings = [HeadingItem(level=1, text="H1"), HeadingItem(level=2, text="H2")]
    links = [LinkItem(text="L1", url="https://example.com")]

    metrics = calculate_metrics(text, paragraphs, headings, links)
    assert metrics["paragraph_count"] == 3
    assert metrics["heading_count"] == 2
    assert metrics["link_count"] == 1
    assert metrics["character_count"] == len(text)
