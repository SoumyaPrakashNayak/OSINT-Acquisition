"""HTML parsing, boilerplate elimination, heading, link, and article body extraction."""

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Comment, Tag

from app.discovery.url_utils import is_valid_url
from app.extraction.metadata import normalize_whitespace
from app.extraction.models import HeadingItem, LinkItem

# Elements that never contain visible human-readable article content
NON_CONTENT_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "iframe"}

# Class/ID/role patterns indicating common non-content boilerplate widgets
BOILERPLATE_PATTERNS = [
    r"\bnav\b",
    r"\bnavbar\b",
    r"\bmenu\b",
    r"\bfooter\b",
    r"\bsidebar\b",
    r"\bcookie\b",
    r"\badvertisement\b",
    r"\bads?\b",
    r"\bad[-_]?(?:container|box|banner|wrapper|slot|unit|placement)\b",
    r"\bbanner[-_]?ad\b",
    r"\bsocial[-_]?share\b",
    r"\bnewsletter\b",
    r"\bwidget\b",
    r"\bpopup\b",
]
BOILERPLATE_REGEX = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

CONTENT_CONTAINER_PATTERNS = [
    r"article[-_]?body",
    r"post[-_]?content",
    r"entry[-_]?content",
    r"story[-_]?body",
    r"main[-_]?content",
]
CONTENT_REGEX = re.compile("|".join(CONTENT_CONTAINER_PATTERNS), re.IGNORECASE)


def parse_html_safe(html: str) -> BeautifulSoup:
    """Safely parse HTML markup into a passive BeautifulSoup DOM using standard html.parser."""
    if not html:
        return BeautifulSoup("", "html.parser")
    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup
    except Exception:
        # Graceful repair fallback
        return BeautifulSoup(f"<html><body>{html}</body></html>", "html.parser")


def clean_dom_tree(soup: BeautifulSoup) -> None:
    """Strip script, style, comments, and boilerplate in-place from the BeautifulSoup DOM."""
    # 1. Remove comments
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # 2. Remove non-content tags
    for tag in soup.find_all(NON_CONTENT_TAGS):
        tag.decompose()

    # 3. Remove semantic boilerplate structures: <nav>, <footer>, <aside>
    for tag in soup.find_all(["nav", "footer", "aside"]):
        tag.decompose()

    # 4. Remove widgets with explicit non-content classes or roles
    for tag in soup.find_all(lambda t: isinstance(t, Tag)):
        if getattr(tag, "attrs", None) is None:
            continue

        role = str(tag.get("role") or "").lower()
        if role in ("navigation", "contentinfo", "complementary", "banner"):
            # Preserve header if it contains h1
            if tag.name == "header" and tag.find("h1"):
                continue
            tag.decompose()
            continue

        raw_classes = tag.get("class") or []
        classes = " ".join(raw_classes) if isinstance(raw_classes, list) else str(raw_classes)
        tag_id = str(tag.get("id") or "")
        identifier = f"{classes} {tag_id}".strip()

        # If it matches boilerplate patterns and doesn't match content container patterns
        if BOILERPLATE_REGEX.search(identifier) and not CONTENT_REGEX.search(identifier):
            # Do not decompose article or main even if styled with something matching
            if tag.name not in ("article", "main", "body", "html"):
                tag.decompose()


def extract_headings(soup: BeautifulSoup) -> list[HeadingItem]:
    """Extract h1-h6 headings in document order, ignoring empty headings."""
    headings: list[HeadingItem] = []
    heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    for tag in heading_tags:
        text = normalize_whitespace(tag.get_text())
        if not text:
            continue
        try:
            level = int(tag.name[1])
            headings.append(HeadingItem(level=level, text=text))
        except (ValueError, IndexError):
            continue

    return headings


def find_main_container(soup: BeautifulSoup) -> tuple[Tag, str]:
    """Identify the primary content container with deterministic fallback.

    Returns:
        tuple[Tag, str]: (content_container_tag, strategy_name)
    """
    # Strategy 1: <article> tag
    article = soup.find("article")
    if article and len(article.get_text(strip=True)) > 30:
        return article, "deterministic_html_article"

    # Strategy 2: <main> tag
    main = soup.find("main")
    if main and len(main.get_text(strip=True)) > 30:
        return main, "deterministic_html_main"

    # Strategy 3: Common class/id containers
    for tag in soup.find_all(["div", "section"]):
        ident = f"{' '.join(tag.get('class', []))} {tag.get('id', '')}"
        if CONTENT_REGEX.search(ident) and len(tag.get_text(strip=True)) > 50:
            return tag, "deterministic_html_container"

    # Strategy 4: <body> fallback
    body = soup.find("body") or soup
    return body, "deterministic_html_body_fallback"


def extract_paragraphs_and_text(container: Tag) -> tuple[list[str], str]:
    """Extract cleaned paragraphs and assembled visible body text from container.

    Returns:
        tuple[list[str], str]: (paragraphs, formatted_visible_text)
    """
    paragraphs: list[str] = []

    # Try paragraph tags first
    p_tags = container.find_all("p")
    for p in p_tags:
        clean = normalize_whitespace(p.get_text())
        if clean and len(clean) > 5:
            # Filter out generic tiny UI strings like 'share', 'menu'
            paragraphs.append(clean)

    # If no <p> tags or insufficient content, extract visible block strings
    if not paragraphs:
        raw_text = container.get_text(separator="\n")
        lines = [normalize_whitespace(line) for line in raw_text.split("\n")]
        paragraphs = [line for line in lines if line and len(line) > 15]

    text = "\n\n".join(paragraphs) if paragraphs else ""
    return paragraphs, text


def extract_links(
    container: Tag, base_url: str, max_links: int = 100
) -> list[LinkItem]:
    """Extract valid HTTP/HTTPS links, resolve relative URLs, and deduplicate."""
    links: list[LinkItem] = []
    seen_urls: set[str] = set()

    for a in container.find_all("a", href=True):
        raw_href = a["href"].strip()
        if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        resolved = urljoin(base_url, raw_href)
        # Verify valid HTTP/HTTPS URL
        parsed = urlparse(resolved)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            continue

        if resolved in seen_urls:
            continue

        text = normalize_whitespace(a.get_text()) or a.get("title") or ""
        seen_urls.add(resolved)
        links.append(LinkItem(text=text, url=resolved))

        if len(links) >= max_links:
            break

    return links
