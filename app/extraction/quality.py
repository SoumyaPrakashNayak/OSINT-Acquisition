"""Content quality measurement and volume metrics calculation."""

import re
from app.config import settings
from app.extraction.models import ContentQuality


def calculate_metrics(text: str, paragraphs: list[str], headings: list, links: list) -> dict:
    """Calculate deterministic content quality and size metrics.

    Args:
        text: Normalized visible body text.
        paragraphs: List of extracted paragraphs.
        headings: List of extracted HeadingItems.
        links: List of extracted LinkItems.

    Returns:
        dict: Metrics dictionary containing counts and ContentQuality enum.
    """
    clean_text = text.strip()
    words = re.findall(r"\b\w+\b", clean_text)
    word_count = len(words)
    char_count = len(clean_text)

    min_words = getattr(settings, "min_content_words", 50)
    high_words = getattr(settings, "high_content_words", 200)

    if word_count == 0:
        quality = ContentQuality.EMPTY
    elif word_count < min_words:
        quality = ContentQuality.LOW
    elif word_count < high_words:
        quality = ContentQuality.MEDIUM
    else:
        quality = ContentQuality.HIGH

    return {
        "content_length": char_count,
        "character_count": char_count,
        "word_count": word_count,
        "paragraph_count": len(paragraphs),
        "heading_count": len(headings),
        "link_count": len(links),
        "content_quality": quality,
    }
