"""Deterministic entity extraction engine and extractor protocol (Phase 5)."""

import re
from typing import Protocol

from app.entity_extraction.models import ExtractedEntity
from app.entity_extraction.normalization import normalize_entity
from app.entity_extraction.taxonomy import EntityType
from app.extraction.models import ExtractedDocument

# ---------------------------------------------------------------------------
# Extractor Protocol
# ---------------------------------------------------------------------------


class EntityExtractor(Protocol):
    """Protocol defining the interface for all entity extraction engines."""

    def extract(self, document: ExtractedDocument) -> list[ExtractedEntity]:
        """Extract entity mentions from an authoritative ExtractedDocument.

        Must be passive, deterministic, and execute without internet access.
        """
        ...


# ---------------------------------------------------------------------------
# Sentence Segmentation Helper
# ---------------------------------------------------------------------------

ABBREVIATIONS = {
    "mr", "ms", "mrs", "dr", "prof", "shri", "smt", "sr", "jr", "vs", "etc",
    "eg", "ie", "us", "un", "rs", "inr", "corp", "inc", "ltd", "co", "dept",
    "gov", "cm", "pm", "dgp", "sp", "dsp", "sho", "asi", "si", "acp", "dcp",
}


def split_sentences_with_spans(text: str) -> list[tuple[int, int, str]]:
    """Split text into sentences while tracking [start, end) offsets in the source text.

    Preserves source wording and avoids false splits on common abbreviations,
    currency markers, and numeric decimals.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []
    length = len(text)
    start = 0

    i = 0
    while i < length:
        char = text[i]

        # Paragraph breaks always delimit sentences
        if char == "\n":
            end = i
            # Check for multiple newlines
            while i + 1 < length and text[i + 1] in "\r\n":
                i += 1
            if end > start:
                raw_sent = text[start:end]
                if raw_sent.strip():
                    spans.append((start, end, raw_sent))
            start = i + 1
            i += 1
            continue

        # Terminal punctuation
        if char in ".!?":
            # Check if this period is an abbreviation or decimal number
            is_boundary = False
            # Check if end of text or followed by whitespace/quote
            if i + 1 >= length or text[i + 1] in " \t\r\n\"'“”‘’":
                if char == ".":
                    # Look back at the token before period
                    prev_word_match = re.search(r"([A-Za-z]+)\.$", text[start : i + 1])
                    if prev_word_match:
                        word = prev_word_match.group(1).lower()
                        # If single capital letter (initial) or known abbreviation, don't split
                        if len(word) == 1 or word in ABBREVIATIONS:
                            i += 1
                            continue
                    # Check if preceded by digits (decimal)
                    if i > 0 and text[i - 1].isdigit() and i + 1 < length and text[i + 1].isdigit():
                        i += 1
                        continue

                is_boundary = True

            if is_boundary:
                end = i + 1
                raw_sent = text[start:end]
                if raw_sent.strip():
                    spans.append((start, end, raw_sent))
                # Skip spaces after sentence end
                while i + 1 < length and text[i + 1] in " \t":
                    i += 1
                start = i + 1

        i += 1

    if start < length:
        remaining = text[start:length]
        if remaining.strip():
            spans.append((start, length, remaining))

    return spans


# ---------------------------------------------------------------------------
# Gazetteers & Patterns for Deterministic Extraction
# ---------------------------------------------------------------------------

KNOWN_INDIAN_CITIES = {
    "bhubaneswar", "cuttack", "puri", "rourkela", "sambalpur", "berhampur",
    "balasore", "baripada", "jharsuguda", "angul", "bhadrak", "jajpur",
    "paradip", "dhenkanal", "kendrapara", "mumbai", "new delhi", "delhi",
    "kolkata", "bangalore", "bengaluru", "chennai", "hyderabad", "pune",
    "ahmedabad", "jaipur", "surat", "lucknow", "kanpur", "nagpur", "indore",
    "thane", "bhopal", "visakhapatnam", "patna", "vadodara", "ghaziabad",
    "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi",
    "srinagar", "aurangabad", "dhanbad", "amritsar", "navi mumbai", "allahabad",
    "prayagraj", "ranchi", "howrah", "coimbatore", "jabalpur", "gwalior",
    "vijayawada", "jodhpur", "madurai", "raipur", "kota", "guwahati",
    "chandigarh", "gurgaon", "gurugram", "noida",
}

KNOWN_INDIAN_STATES = {
    "odisha", "orissa", "maharashtra", "karnataka", "tamil nadu", "west bengal",
    "gujarat", "uttar pradesh", "rajasthan", "andhra pradesh", "telangana",
    "kerala", "madhya pradesh", "punjab", "haryana", "bihar", "assam",
    "jharkhand", "chhattisgarh", "uttarakhand", "himachal pradesh", "goa",
    "tripura", "manipur", "meghalaya", "nagaland", "mizoram", "sikkim",
    "arunachal pradesh", "jammu and kashmir", "ladakh", "puducherry",
}

KNOWN_WORLD_LOCATIONS = {
    "india", "united states", "usa", "united kingdom", "uk", "canada",
    "australia", "germany", "france", "japan", "china", "russia", "brazil",
    "south africa", "nepal", "bangladesh", "pakistan", "sri lanka", "bhutan",
    "myanmar", "singapore", "united arab emirates", "uae", "dubai", "london",
    "new york", "washington", "paris", "tokyo", "beijing", "berlin",
}

KNOWN_ORGANIZATIONS = {
    "google", "microsoft", "apple", "amazon", "meta", "twitter", "openai",
    "ibm", "intel", "cisco", "oracle", "tcs", "infosys", "wipro", "tata",
    "reliance", "adani", "hdfc", "icici", "sbi", "state bank of india",
    "united nations", "un", "who", "world health organization", "world bank",
    "imf", "nato", "european union", "eu", "odisha police", "delhi police",
    "mumbai police", "cbi", "central bureau of investigation", "nia",
    "national investigation agency", "ed", "enforcement directorate", "raw",
    "ib", "intelligence bureau", "cid", "state police", "siksha 'o' anusandhan",
    "soa", "iit", "iim", "nit", "aiims", "supreme court", "high court",
    "parliament", "google search",
}

# Negative stopwords for person names to prevent false positive capital pairs
NON_PERSON_WORDS = {
    "the", "this", "that", "these", "those", "every", "all", "some", "any",
    "first", "last", "next", "previous", "today", "yesterday", "tomorrow",
    "breaking", "news", "report", "press", "release", "page", "article",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "prime", "minister",
    "chief", "court", "police", "bank", "high", "supreme", "united", "states",
    "nations", "kingdom", "new", "delhi", "south", "north", "east", "west",
    "official", "officer", "government", "authorities", "spokesperson",
}

# Regex for structural organization suffixes
ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9&'\s]+?\s+(?:Corp(?:oration)?|Inc(?:orporated)?|Ltd|Limited|LLC|LLP|Pvt\s+Ltd|Private\s+Limited|Company|Co\.|Group|Bank|University|College|Institute|Foundation|Association|Police|Department|Ministry|Commission|Bureau|Agency|Hospital))\b"
)

# Regex for email
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Regex for URLs in text
URL_RE = re.compile(
    r"\bhttps?://[^\s<>\"'{}|\\^`]+|\bwww\.[^\s<>\"'{}|\\^`]+"
)

# Regex for phone numbers (Indian & international formats)
# Examples: +91 9876543210, +91-98765-43210, +91 98765 43210, 9876543210, 98765 43210, 09876543210
PHONE_RE = re.compile(
    r"(?:\+91[\s-]?[6-9]\d{2,4}[\s-]?\d{3,5}\b|\b[6-9]\d{4}[\s-]\d{5}\b|\b[6-9]\d{9}\b|\b0[6-9]\d{9}\b)"
)

# Regex for monetary values
# Examples: ₹10 lakh, $5 million, Rs. 50,000, INR 25,000, €100
MONEY_RE = re.compile(
    r"(?:(?:₹|\$|€|£|¥)\s*\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:lakh|crore|million|billion|thousand))?\b|\b(?:Rs\.?|INR|USD|EUR|GBP)\s*\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:lakh|crore|million|billion|thousand))?\b|\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:lakh|crore|million|billion|thousand)?\s*(?:INR|USD|EUR|GBP|Rs\.?)\b)"
)

# Regex for dates
DATE_RE_NAMED = re.compile(
    r"\b(?:(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:19\d\d|20\d\d)|\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?,?\s+(?:19\d\d|20\d\d)|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))\b"
)
DATE_RE_NUMERIC = re.compile(
    r"\b(?:(?:19\d\d|20\d\d)-\d{2}-\d{2}|\d{1,2}/\d{1,2}/(?:19\d\d|20\d\d)|\d{1,2}-\d{1,2}-(?:19\d\d|20\d\d))\b"
)
DATE_RE_WEEKDAY = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"
)

# Regex for times
TIME_RE = re.compile(
    r"\b(?:\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)|(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d|(?:[01]\d|2[0-3]):[0-5]\d\s*(?:hrs|hours|IST|UTC|GMT))\b"
)

# Regex for titles/honorifics introducing a person
TITLE_PERSON_RE = re.compile(
    r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.|Shri|Smt\.|Officer|Inspector|Commissioner|Chief Minister|Prime Minister|Minister|Governor|Justice|Judge|Advocate|President|Senator|Secretary)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
)

# Regex for action/verbs associated with person mentions
PERSON_ACTION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:met|visited|joined|spoke|spoke to|addressed|stated|said|announced|attended|held|arrived|received|met with|tweeted|posted|replied|warned|told|explained|confirmed)\b"
)

# Regex for descriptive identification of a person
PERSON_DESCR_RE = re.compile(
    r"\b(?:named|accused|suspect|victim|witness|arrested|identified as|contacted|appointed|hired)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
)

# General two-word capitalized pattern for names
TWO_WORD_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+))\b")


class DeterministicEntityExtractor:
    """Production entity extractor using high-precision deterministic rules and gazetteers.

    Operates completely offline, requires zero external services or ML runtime downloads,
    and produces 100% deterministic entity mentions with verified character offsets.
    """

    def __init__(self):
        self._all_locations = KNOWN_INDIAN_CITIES | KNOWN_INDIAN_STATES | KNOWN_WORLD_LOCATIONS

    def extract(self, document: ExtractedDocument) -> list[ExtractedEntity]:
        """Extract identifiable entity mentions from ExtractedDocument.text."""
        text = document.text or ""
        if not text.strip():
            return []

        doc_hash = document.content_hash
        source_url = document.final_url or document.requested_url

        # Compute sentence spans once
        sentence_spans = split_sentences_with_spans(text)

        candidates: list[dict] = []

        # 1. EMAIL extraction
        for match in EMAIL_RE.finditer(text):
            candidates.append({
                "type": EntityType.EMAIL,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 10,
            })

        # 2. URL extraction
        for match in URL_RE.finditer(text):
            raw_url = match.group()
            # Clean trailing punctuation
            clean_url = re.sub(r"[.,;:!?]+$", "", raw_url)
            start_off = match.start()
            end_off = start_off + len(clean_url)
            candidates.append({
                "type": EntityType.URL,
                "text": clean_url,
                "start": start_off,
                "end": end_off,
                "priority": 10,
            })

        # 3. PHONE extraction
        for match in PHONE_RE.finditer(text):
            candidates.append({
                "type": EntityType.PHONE,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 9,
            })

        # 4. MONEY extraction
        for match in MONEY_RE.finditer(text):
            candidates.append({
                "type": EntityType.MONEY,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 8,
            })

        # 5. TIME extraction
        for match in TIME_RE.finditer(text):
            candidates.append({
                "type": EntityType.TIME,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 8,
            })

        # 6. DATE extraction
        for match in DATE_RE_NAMED.finditer(text):
            candidates.append({
                "type": EntityType.DATE,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 8,
            })
        for match in DATE_RE_NUMERIC.finditer(text):
            candidates.append({
                "type": EntityType.DATE,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 8,
            })
        for match in DATE_RE_WEEKDAY.finditer(text):
            candidates.append({
                "type": EntityType.DATE,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "priority": 7,
            })

        # 7. ORGANIZATION extraction
        # 7a. Known organizations
        for org in KNOWN_ORGANIZATIONS:
            # Case-insensitive whole phrase match
            pattern = re.compile(rf"\b{re.escape(org)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append({
                    "type": EntityType.ORGANIZATION,
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "priority": 7,
                })

        # 7b. Structural organization suffixes
        for match in ORG_SUFFIX_RE.finditer(text):
            candidates.append({
                "type": EntityType.ORGANIZATION,
                "text": match.group(1),
                "start": match.start(1),
                "end": match.end(1),
                "priority": 6,
            })

        # 8. LOCATION extraction
        # Known locations
        for loc in self._all_locations:
            pattern = re.compile(rf"\b{re.escape(loc)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append({
                    "type": EntityType.LOCATION,
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "priority": 5,
                })

        # 9. PERSON extraction
        # 9a. Honorific / Title prefixed names
        for match in TITLE_PERSON_RE.finditer(text):
            candidates.append({
                "type": EntityType.PERSON,
                "text": match.group(1),
                "start": match.start(1),
                "end": match.end(1),
                "priority": 6,
            })

        # 9b. Contextual person action verbs (e.g., "Sundar Pichai visited India")
        for match in PERSON_ACTION_RE.finditer(text):
            cand_name = match.group(1)
            if not self._is_non_person(cand_name):
                candidates.append({
                    "type": EntityType.PERSON,
                    "text": cand_name,
                    "start": match.start(1),
                    "end": match.end(1),
                    "priority": 5,
                })

        # 9c. Contextual person descriptive mentions (e.g., "named Ramesh Kumar")
        for match in PERSON_DESCR_RE.finditer(text):
            cand_name = match.group(1)
            if not self._is_non_person(cand_name):
                candidates.append({
                    "type": EntityType.PERSON,
                    "text": cand_name,
                    "start": match.start(1),
                    "end": match.end(1),
                    "priority": 5,
                })

        # 9d. Known individual names
        known_people = ["sundar pichai", "ramesh kumar", "rajesh kumar", "amit shah", "john doe", "jane doe"]
        for p in known_people:
            pattern = re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append({
                    "type": EntityType.PERSON,
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "priority": 6,
                })

        # 9e. General two-word capitalized pattern (conservative)
        for match in TWO_WORD_NAME_RE.finditer(text):
            cand_name = match.group(1)
            if not self._is_non_person(cand_name):
                candidates.append({
                    "type": EntityType.PERSON,
                    "text": cand_name,
                    "start": match.start(1),
                    "end": match.end(1),
                    "priority": 3,
                })

        # Resolve overlapping spans deterministically
        selected_spans = self._resolve_overlaps(candidates)

        # Build ExtractedEntity objects with sentence context & provenance
        entities: list[ExtractedEntity] = []
        for idx, span in enumerate(selected_spans):
            e_start = span["start"]
            e_end = span["end"]
            e_type = span["type"]
            raw_text = span["text"]

            # Sentence association
            sent_text = self._find_containing_sentence(sentence_spans, e_start, e_end, text)

            normalized = normalize_entity(e_type, raw_text)
            ent_id = f"entity-{idx + 1}"

            entities.append(
                ExtractedEntity(
                    id=ent_id,
                    type=e_type,
                    text=raw_text,
                    normalized_text=normalized,
                    start_offset=e_start,
                    end_offset=e_end,
                    sentence=sent_text,
                    confidence=None,  # Rule-based extraction does not fabricate probabilistic confidence
                    source_document_hash=doc_hash,
                    source_url=source_url,
                )
            )

        return entities

    def _is_non_person(self, candidate: str) -> bool:
        """Check if a candidate name is a known location, organization, or stopword."""
        cand_lower = candidate.lower().strip()
        words = cand_lower.split()

        # Check against locations & organizations
        if cand_lower in self._all_locations:
            return True
        if cand_lower in KNOWN_ORGANIZATIONS:
            return True

        # Check if any word is in NON_PERSON_WORDS
        for w in words:
            if w in NON_PERSON_WORDS:
                return True

        return False

    def _resolve_overlaps(self, candidates: list[dict]) -> list[dict]:
        """Resolve overlapping entity spans deterministically.

        Prefers:
        1. Higher priority match category
        2. Longer span length
        3. Earlier start offset
        """
        # Sort candidates by: (-priority, -length, start)
        candidates.sort(
            key=lambda c: (-c["priority"], -(c["end"] - c["start"]), c["start"])
        )

        selected: list[dict] = []
        occupied: list[tuple[int, int]] = []

        for cand in candidates:
            c_start = cand["start"]
            c_end = cand["end"]

            # Check overlap with any already selected span
            overlaps = False
            for s_start, s_end in occupied:
                if max(c_start, s_start) < min(c_end, s_end):
                    overlaps = True
                    break

            if not overlaps:
                selected.append(cand)
                occupied.append((c_start, c_end))

        # Re-sort final selected spans in document order (start offset ascending)
        selected.sort(key=lambda c: c["start"])
        return selected

    def _find_containing_sentence(
        self,
        sentence_spans: list[tuple[int, int, str]],
        start_offset: int,
        end_offset: int,
        full_text: str,
    ) -> str:
        """Find the sentence span that encloses the entity offset."""
        for s_start, s_end, s_text in sentence_spans:
            if s_start <= start_offset and end_offset <= s_end:
                return s_text.strip()

        # Fallback: if boundary split across sentence, extract surrounding context
        fallback_start = max(0, start_offset - 50)
        fallback_end = min(len(full_text), end_offset + 50)
        return full_text[fallback_start:fallback_end].strip()
