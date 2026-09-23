"""Deterministic HTML metadata extraction (title, description, canonical, author, dates, language)."""

import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


def normalize_whitespace(text: str | None) -> str | None:
    """Collapse consecutive whitespace and strip edges."""
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def extract_title(soup: BeautifulSoup) -> str | None:
    """Extract page title following strict priority: <title> -> og:title -> twitter:title -> h1."""
    # 1. <title>
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        clean = normalize_whitespace(title_tag.string)
        if clean:
            return clean

    # 2. og:title
    og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find(
        "meta", attrs={"name": "og:title"}
    )
    if og_title and og_title.get("content"):
        clean = normalize_whitespace(og_title["content"])
        if clean:
            return clean

    # 3. twitter:title
    tw_title = soup.find("meta", attrs={"name": "twitter:title"}) or soup.find(
        "meta", attrs={"property": "twitter:title"}
    )
    if tw_title and tw_title.get("content"):
        clean = normalize_whitespace(tw_title["content"])
        if clean:
            return clean

    # 4. First <h1>
    h1 = soup.find("h1")
    if h1:
        clean = normalize_whitespace(h1.get_text())
        if clean:
            return clean

    return None


def extract_description(soup: BeautifulSoup) -> str | None:
    """Extract description: meta description -> og:description -> twitter:description."""
    # 1. meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        clean = normalize_whitespace(meta_desc["content"])
        if clean:
            return clean

    # 2. og:description
    og_desc = soup.find("meta", attrs={"property": "og:description"}) or soup.find(
        "meta", attrs={"name": "og:description"}
    )
    if og_desc and og_desc.get("content"):
        clean = normalize_whitespace(og_desc["content"])
        if clean:
            return clean

    # 3. twitter:description
    tw_desc = soup.find("meta", attrs={"name": "twitter:description"}) or soup.find(
        "meta", attrs={"property": "twitter:description"}
    )
    if tw_desc and tw_desc.get("content"):
        clean = normalize_whitespace(tw_desc["content"])
        if clean:
            return clean

    return None


def extract_canonical_url(soup: BeautifulSoup, base_url: str) -> str | None:
    """Extract canonical URL link and resolve against base URL."""
    canonical = soup.find("link", attrs={"rel": lambda r: r and "canonical" in r})
    if canonical and canonical.get("href"):
        raw_href = canonical["href"].strip()
        if raw_href:
            return urljoin(base_url, raw_href)
    return None


def _parse_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Extract and parse structured JSON-LD script blocks safely."""
    items: list[dict] = []
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for s in scripts:
        if not s.string:
            continue
        try:
            data = json.loads(s.string)
            if isinstance(data, dict):
                items.append(data)
                # Check @graph array
                if "@graph" in data and isinstance(data["@graph"], list):
                    items.extend([x for x in data["@graph"] if isinstance(x, dict)])
            elif isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict)])
        except Exception:
            continue
    return items


def extract_author(soup: BeautifulSoup) -> str | None:
    """Extract author with byline marker normalization."""
    # 1. meta author
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = _clean_byline(meta_author["content"])
        if author:
            return author

    # 2. article:author
    art_author = soup.find("meta", attrs={"property": "article:author"}) or soup.find(
        "meta", attrs={"name": "article:author"}
    )
    if art_author and art_author.get("content"):
        author = _clean_byline(art_author["content"])
        if author:
            return author

    # 3. JSON-LD author
    for item in _parse_json_ld(soup):
        if "author" in item:
            auth_val = item["author"]
            if isinstance(auth_val, dict) and "name" in auth_val:
                author = _clean_byline(auth_val["name"])
                if author:
                    return author
            elif isinstance(auth_val, str):
                author = _clean_byline(auth_val)
                if author:
                    return author
            elif isinstance(auth_val, list) and auth_val:
                first = auth_val[0]
                if isinstance(first, dict) and "name" in first:
                    author = _clean_byline(first["name"])
                    if author:
                        return author
                elif isinstance(first, str):
                    author = _clean_byline(first)
                    if author:
                        return author

    # 4. Byline or author class/attribute
    author_elem = soup.find(
        lambda tag: tag.name in ("span", "div", "p", "a")
        and (
            "author" in tag.get("class", [])
            or "byline" in tag.get("class", [])
            or tag.get("rel") == ["author"]
        )
    )
    if author_elem:
        author = _clean_byline(author_elem.get_text())
        if author:
            return author

    return None


def _clean_byline(raw: str | None) -> str | None:
    """Normalize byline text, stripping leading 'By ' or 'by ' prefix."""
    clean = normalize_whitespace(raw)
    if not clean:
        return None
    # Strip "By " or "by " prefix
    stripped = re.sub(r"^(?:by|By)\s+", "", clean).strip()
    return stripped if stripped else None


def _parse_iso_date(raw_date: str | None) -> str | None:
    """Parse raw date string and return normalized ISO-8601 representation."""
    if not raw_date:
        return None
    clean = raw_date.strip()
    if not clean:
        return None
    try:
        dt = date_parser.parse(clean)
        return dt.isoformat()
    except Exception:
        return None


def extract_dates(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Extract publication date and modified date in ISO-8601 format.

    Returns:
        tuple[str | None, str | None]: (publication_date, modified_date)
    """
    pub_date: str | None = None
    mod_date: str | None = None

    # Check JSON-LD first for structured dates
    for item in _parse_json_ld(soup):
        if not pub_date and "datePublished" in item and isinstance(item["datePublished"], str):
            pub_date = _parse_iso_date(item["datePublished"])
        if not mod_date and "dateModified" in item and isinstance(item["dateModified"], str):
            mod_date = _parse_iso_date(item["dateModified"])

    # Fallback to meta tags for publication date
    if not pub_date:
        date_meta = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "article:published_time"})
            or soup.find("meta", attrs={"name": "publication_date"})
            or soup.find("meta", attrs={"name": "publish-date"})
            or soup.find("meta", attrs={"name": "pubdate"})
            or soup.find("meta", attrs={"name": "date"})
        )
        if date_meta and date_meta.get("content"):
            pub_date = _parse_iso_date(date_meta["content"])

    # Fallback to <time datetime="...">
    if not pub_date:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            pub_date = _parse_iso_date(time_tag["datetime"])

    # Fallback to meta tags for modified date
    if not mod_date:
        mod_meta = (
            soup.find("meta", attrs={"property": "article:modified_time"})
            or soup.find("meta", attrs={"name": "article:modified_time"})
            or soup.find("meta", attrs={"name": "last-modified"})
            or soup.find("meta", attrs={"name": "modified"})
        )
        if mod_meta and mod_meta.get("content"):
            mod_date = _parse_iso_date(mod_meta["content"])

    return pub_date, mod_date


def extract_language(soup: BeautifulSoup) -> str | None:
    """Extract language metadata from html tag or meta headers."""
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        clean = normalize_whitespace(html_tag["lang"])
        if clean:
            return clean

    meta_lang = soup.find("meta", attrs={"http-equiv": "content-language"}) or soup.find(
        "meta", attrs={"name": "language"}
    )
    if meta_lang and meta_lang.get("content"):
        clean = normalize_whitespace(meta_lang["content"])
        if clean:
            return clean

    return None
