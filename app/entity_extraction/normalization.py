"""Conservative entity normalization functions for Phase 5."""

import re
from urllib.parse import urlparse, urlunparse

from app.entity_extraction.taxonomy import EntityType

# Pre-compiled regex patterns for normalization
WHITESPACE_RE = re.compile(r"\s+")
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")
PHONE_CLEAN_RE = re.compile(r"[^\d+]")
YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

NAMED_DATE_PATTERN_1 = re.compile(
    r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(19\d\d|20\d\d)\b",
    re.IGNORECASE,
)
NAMED_DATE_PATTERN_2 = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(19\d\d|20\d\d)\b",
    re.IGNORECASE,
)
NUMERIC_DATE_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(19\d\d|20\d\d)\b")
NUMERIC_DATE_ISO = re.compile(r"\b(19\d\d|20\d\d)-(\d{1,2})-(\d{1,2})\b")


def normalize_whitespace(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    if not text:
        return ""
    return WHITESPACE_RE.sub(" ", text.strip())


def normalize_email(email: str) -> str:
    """Normalize email address by stripping whitespace and lowercasing."""
    cleaned = normalize_whitespace(email)
    return cleaned.lower()


def normalize_url(url_str: str) -> str:
    """Normalize URL by stripping whitespace and standardizing scheme/host casing."""
    cleaned = normalize_whitespace(url_str)
    cleaned = TRAILING_PUNCT_RE.sub("", cleaned)
    try:
        parsed = urlparse(cleaned)
        if parsed.scheme and parsed.netloc:
            # Lowercase scheme and netloc only, preserve path/query
            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            ))
            return normalized
    except Exception:
        pass
    return cleaned


def normalize_phone(phone: str) -> str:
    """Normalize phone number by standardizing formatting without querying external services.

    Preserves leading '+' for country codes, removes whitespace, hyphens, and parentheses.
    """
    cleaned = normalize_whitespace(phone)
    has_plus = cleaned.startswith("+")
    digits_only = PHONE_CLEAN_RE.sub("", cleaned)

    if has_plus and not digits_only.startswith("+"):
        return f"+{digits_only}"
    return digits_only


def normalize_money(money_str: str) -> str:
    """Normalize monetary string formatting while preserving currency symbol and magnitude.

    Does not convert currencies or apply exchange rates.
    """
    cleaned = normalize_whitespace(money_str)
    # Standardize space after currency symbol/code: e.g. "₹  10 lakh" -> "₹10 lakh", "Rs.  50,000" -> "Rs. 50,000"
    cleaned = re.sub(r"^(₹|\$|€|£|¥)\s+", r"\1", cleaned)
    cleaned = re.sub(r"^(Rs\.?|INR|USD|EUR|GBP)\s+", r"\1 ", cleaned)
    return cleaned


def normalize_date(date_str: str) -> str:
    """Normalize dates unambiguously without inventing missing years or inferring event dates."""
    cleaned = normalize_whitespace(date_str)
    cleaned = TRAILING_PUNCT_RE.sub("", cleaned)

    # 1. ISO date: YYYY-MM-DD
    iso_match = NUMERIC_DATE_ISO.match(cleaned)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    # 2. Named date: "September 21, 2026"
    match1 = NAMED_DATE_PATTERN_1.match(cleaned)
    if match1:
        month_name, day, year = match1.groups()
        m_num = MONTH_MAP.get(month_name.lower())
        if m_num:
            return f"{int(year):04d}-{m_num:02d}-{int(day):02d}"

    # 3. Named date: "21 September 2026"
    match2 = NAMED_DATE_PATTERN_2.match(cleaned)
    if match2:
        day, month_name, year = match2.groups()
        m_num = MONTH_MAP.get(month_name.lower())
        if m_num:
            return f"{int(year):04d}-{m_num:02d}-{int(day):02d}"

    # 4. Numeric date with slash: DD/MM/YYYY
    slash_match = NUMERIC_DATE_SLASH.match(cleaned)
    if slash_match:
        part1, part2, year = slash_match.groups()
        p1, p2 = int(part1), int(part2)
        # Standardize DD/MM/YYYY (common in Indian OSINT context)
        if p1 > 12 >= p2:  # Definitely DD/MM
            return f"{int(year):04d}-{p2:02d}-{p1:02d}"
        elif p2 > 12 >= p1:  # Definitely MM/DD
            return f"{int(year):04d}-{p1:02d}-{p2:02d}"
        else:
            # Conservative: preserve standard DD/MM/YYYY formatting if unambiguous
            return f"{int(year):04d}-{p2:02d}-{p1:02d}"

    # If missing year (e.g., "September 21") or weekday ("Monday"), return cleaned text as-is
    # Do NOT invent missing years
    return cleaned


def normalize_time(time_str: str) -> str:
    """Normalize time formatting by standardizing whitespace."""
    cleaned = normalize_whitespace(time_str)
    # Standardize whitespace before AM/PM: e.g. "10:30   AM" -> "10:30 AM"
    cleaned = re.sub(r"\s*(AM|PM|am|pm)\b", lambda m: f" {m.group(1).upper()}", cleaned)
    return cleaned


def normalize_entity(entity_type: EntityType, text: str) -> str:
    """Dispatch conservative normalization based on entity type."""
    if not text:
        return ""

    if entity_type == EntityType.EMAIL:
        return normalize_email(text)
    elif entity_type == EntityType.URL:
        return normalize_url(text)
    elif entity_type == EntityType.PHONE:
        return normalize_phone(text)
    elif entity_type == EntityType.MONEY:
        return normalize_money(text)
    elif entity_type == EntityType.DATE:
        return normalize_date(text)
    elif entity_type == EntityType.TIME:
        return normalize_time(text)
    else:
        # PERSON, ORGANIZATION, LOCATION, VEHICLE, FACILITY
        # Clean outer punctuation / quotes, collapse internal whitespace, preserve case
        cleaned = normalize_whitespace(text)
        cleaned = cleaned.strip("\"'“”‘’`")
        return cleaned.strip()
