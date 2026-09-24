"""Tests for conservative entity normalization (Phase 5)."""

from app.entity_extraction.normalization import (
    normalize_date,
    normalize_email,
    normalize_entity,
    normalize_money,
    normalize_phone,
    normalize_time,
    normalize_url,
    normalize_whitespace,
)
from app.entity_extraction.taxonomy import EntityType


def test_normalize_whitespace():
    """Verify whitespace is trimmed and internal runs are collapsed."""
    assert normalize_whitespace("  Sundar   Pichai  ") == "Sundar Pichai"
    assert normalize_whitespace("Google\n  Inc") == "Google Inc"
    assert normalize_whitespace("") == ""


def test_normalize_email():
    """Verify email address normalization strips whitespace and converts to lowercase."""
    assert normalize_email(" JOHN@EXAMPLE.COM ") == "john@example.com"
    assert normalize_email("Investigation.Team@Agency.Gov.In") == "investigation.team@agency.gov.in"


def test_normalize_url():
    """Verify URL normalization cleans trailing punctuation and lowercases scheme/host."""
    assert normalize_url("  HTTPS://EXAMPLE.COM/Path/To/Page.html  ") == "https://example.com/Path/To/Page.html"
    assert normalize_url("http://news.agency.org/article?id=42.") == "http://news.agency.org/article?id=42"


def test_normalize_phone():
    """Verify phone normalization strips formatting characters and preserves leading plus."""
    assert normalize_phone("  +91 98765 43210  ") == "+919876543210"
    assert normalize_phone("+91-98765-43210") == "+919876543210"
    assert normalize_phone("(09876) 543210") == "09876543210"
    assert normalize_phone("98765 43210") == "9876543210"


def test_normalize_money():
    """Verify money normalization standardizes spacing without currency conversions."""
    assert normalize_money("₹  10 lakh") == "₹10 lakh"
    assert normalize_money("Rs.   50,000") == "Rs. 50,000"
    assert normalize_money("$  5 million") == "$5 million"
    assert normalize_money("INR  25,000") == "INR 25,000"


def test_normalize_date():
    """Verify unambiguous dates are normalized to ISO without inventing missing years."""
    # Named dates with 4-digit years
    assert normalize_date("September 21, 2026") == "2026-09-21"
    assert normalize_date("21 September 2026") == "2026-09-21"
    assert normalize_date("21st September 2026") == "2026-09-21"

    # Slash dates: DD/MM/YYYY
    assert normalize_date("21/09/2026") == "2026-09-21"

    # ISO dates
    assert normalize_date("2026-09-21") == "2026-09-21"

    # Day of week preserved
    assert normalize_date("Monday") == "Monday"

    # Date with missing year must NOT invent year
    assert normalize_date("September 21") == "September 21"


def test_normalize_time():
    """Verify time formatting normalizes whitespace before AM/PM."""
    assert normalize_time("10:30   AM") == "10:30 AM"
    assert normalize_time("4:00   pm") == "4:00 PM"
    assert normalize_time("10:30:00") == "10:30:00"


def test_normalize_entity_dispatch():
    """Verify dispatcher properly normalizes each entity type."""
    assert normalize_entity(EntityType.PERSON, "  'Sundar Pichai'  ") == "Sundar Pichai"
    assert normalize_entity(EntityType.ORGANIZATION, "  \"Google\"  ") == "Google"
    assert normalize_entity(EntityType.LOCATION, "  Bhubaneswar,  ") == "Bhubaneswar,"
    assert normalize_entity(EntityType.EMAIL, " ADMIN@CORP.IN ") == "admin@corp.in"
    assert normalize_entity(EntityType.PHONE, "+91 98765-43210") == "+919876543210"
