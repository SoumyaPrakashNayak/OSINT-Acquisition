"""End-to-End OSINT Pipeline Demonstration Script.

Runs the complete sequence:
Target -> QueryGenerator -> SearchProvider -> Candidate URLs -> WebFetcher -> ExtractedDocument

Can run with:
1. Deterministic offline mocks (zero external dependencies)
2. Live search engines (SearXNG, SerpAPI, Tavily)
3. Direct live URL extraction (fetches and extracts any real website)
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure repository root is in python search path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.acquisition.fetcher import HttpWebFetcher
from app.acquisition.mock_fetcher import MockWebFetcher
from app.acquisition.models import WebDocument
from app.acquisition.service import AcquisitionService
from app.config import settings
from app.discovery.http_provider import HttpSearchProvider
from app.discovery.mock_provider import MockSearchProvider
from app.discovery.query_generator import QueryGenerator
from app.discovery.service import DiscoveryService
from app.extraction.service import ExtractionService
from app.models.schemas import TargetPerson


def banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


async def run_pipeline(
    name: str,
    location: str | None,
    organization: str | None,
    keywords: list[str],
    provider_name: str,
    api_key: str | None,
    api_url: str | None,
    use_real_fetcher: bool,
    direct_url: str | None = None,
):
    banner("OSINT INTELLIGENCE COMPONENT - END-TO-END DEMO")

    # If direct URL is provided, skip discovery and demonstrate live fetch + extraction
    if direct_url:
        print(f"\n[Mode] Direct URL Acquisition & Extraction: {direct_url}")
        fetcher = HttpWebFetcher() if use_real_fetcher else MockWebFetcher()
        acq_service = AcquisitionService(fetcher=fetcher)

        banner("STEP 1: ACQUIRING WEB CONTENT")
        print(f"Fetching: {direct_url} using {fetcher.__class__.__name__}...")
        fetch_res = await acq_service.acquire(direct_url)

        if not fetch_res.success or not fetch_res.document:
            print(f"\n[-] Acquisition Failed:")
            print(f"    Code: {fetch_res.error.code if fetch_res.error else 'UNKNOWN'}")
            print(f"    Message: {fetch_res.error.message if fetch_res.error else 'None'}")
            return

        web_doc = fetch_res.document
        _print_web_document(web_doc)

        banner("STEP 2: EXTRACTING ARTICLE CONTENT (PHASE 4)")
        extraction_service = ExtractionService()
        extract_res = extraction_service.extract(web_doc)

        if not extract_res.success or not extract_res.document:
            print(f"\n[-] Extraction Failed:")
            print(f"    Code: {extract_res.error.code if extract_res.error else 'UNKNOWN'}")
            print(f"    Message: {extract_res.error.message if extract_res.error else 'None'}")
            return

        _print_extracted_document(extract_res.document)
        return

    # STEP 1: Define Target Person
    banner("STEP 1: TARGET PERSON IDENTIFIERS")
    target = TargetPerson(
        name=name,
        location=location,
        organization=organization,
        keywords=keywords,
    )
    print(json.dumps(target.model_dump(exclude_none=True), indent=2))

    # STEP 2: Generate Deterministic Queries
    banner("STEP 2: DETERMINISTIC QUERY GENERATION")
    query_gen = QueryGenerator()
    queries = query_gen.generate(target)
    print(f"Synthesized {len(queries)} prioritized search queries:")
    for idx, q in enumerate(queries, 1):
        print(f"  [{idx:02d}] {q}")

    # STEP 3: Execute Search Discovery
    banner(f"STEP 3: CANDIDATE SEARCH DISCOVERY (Provider: {provider_name.upper()})")
    if provider_name.lower() == "mock":
        provider = MockSearchProvider()
    else:
        provider = HttpSearchProvider(
            provider_type=provider_name.lower(),
            api_key=api_key or settings.search_api_key,
            api_url=api_url or settings.search_api_url,
        )

    discovery_service = DiscoveryService(search_provider=provider)
    print(f"Executing queries with {provider.__class__.__name__}...")
    discovery_res = await discovery_service.discover(target)

    print(f"\nDiscovered {discovery_res.total_results} candidate public web sources:")
    for idx, result in enumerate(discovery_res.results, 1):
        print(f"\n  [{idx}] {result.title}")
        print(f"      URL:    {result.url}")
        print(f"      Source: {result.source}")
        if result.snippet:
            print(f"      Snippet: {result.snippet[:120]}...")

    if not discovery_res.results:
        print("\n[-] No candidate search results found to acquire.")
        return

    # STEP 4: Select Candidate URL
    selected_result = discovery_res.results[0]
    banner("STEP 4: SELECTING CANDIDATE URL FOR ACQUISITION")
    print(f"Selected Candidate: {selected_result.title}")
    print(f"Target URL:         {selected_result.url}")

    # STEP 5: Web Content Acquisition
    banner(f"STEP 5: ACQUIRING WEB DOCUMENT (Fetcher: {'HTTP (LIVE)' if use_real_fetcher else 'MOCK'})")
    if use_real_fetcher:
        fetcher = HttpWebFetcher()
    else:
        fetcher = MockWebFetcher()

    acq_service = AcquisitionService(fetcher=fetcher)
    fetch_res = await acq_service.acquire(selected_result.url)

    if not fetch_res.success or not fetch_res.document:
        print(f"\n[-] Acquisition Failed:")
        print(f"    Code: {fetch_res.error.code if fetch_res.error else 'UNKNOWN'}")
        print(f"    Message: {fetch_res.error.message if fetch_res.error else 'None'}")
        return

    web_doc = fetch_res.document
    _print_web_document(web_doc)

    # STEP 6: Phase 4 Content Extraction
    banner("STEP 6: EXTRACTING STRUCTURED CONTENT (PHASE 4)")
    extraction_service = ExtractionService()
    extract_res = extraction_service.extract(web_doc)

    if not extract_res.success or not extract_res.document:
        print(f"\n[-] Extraction Failed:")
        print(f"    Code: {extract_res.error.code if extract_res.error else 'UNKNOWN'}")
        print(f"    Message: {extract_res.error.message if extract_res.error else 'None'}")
        return

    _print_extracted_document(extract_res.document)


def _print_web_document(web_doc: WebDocument):
    print(f"Status:         HTTP {web_doc.status_code}")
    print(f"Final URL:      {web_doc.final_url}")
    print(f"Host Domain:    {web_doc.domain}")
    print(f"Content Type:   {web_doc.content_type}")
    print(f"Content Length: {web_doc.content_length} bytes")
    print(f"Retrieved At:   {web_doc.retrieved_at.isoformat()}")
    print(f"SHA-256 Hash:   {web_doc.content_hash}")
    print(f"Raw HTML Size:  {len(web_doc.html)} characters")


def _print_extracted_document(doc):
    banner("STEP 7: EXTRACTED ARTICLE & INTELLIGENCE REPORT")
    print(f"Title:            {doc.title or '[No Title Detected]'}")
    print(f"Author / Byline:  {doc.author or '[No Author Detected]'}")
    print(f"Publication Date: {doc.publication_date or '[Unknown]'}")
    print(f"Modified Date:    {doc.modified_date or '[Unknown]'}")
    print(f"Language:         {doc.language or '[Unknown]'}")
    print(f"Canonical URL:    {doc.canonical_url or '[None]'}")
    print(f"Method:           {doc.extraction_method}")
    print(f"Quality Rating:   {doc.content_quality.value}")
    print(f"Volume Metrics:   {doc.word_count} words | {doc.character_count} chars | {doc.paragraph_count} paragraphs")
    print(f"Headings Count:   {doc.heading_count}")
    print(f"Hyperlinks Found: {doc.link_count}")

    if doc.headings:
        print("\n--- Document Headings Hierarchy ---")
        for h in doc.headings[:6]:
            indent = "  " * (h.level - 1)
            print(f"{indent}H{h.level}: {h.text}")

    print("\n--- Extracted Clean Article Body Preview ---")
    if doc.paragraphs:
        for idx, p in enumerate(doc.paragraphs[:4], 1):
            print(f"[{idx}] {p}\n")
        if len(doc.paragraphs) > 4:
            print(f"... [{len(doc.paragraphs) - 4} additional paragraphs omitted] ...")
    else:
        print(doc.text[:600] if doc.text else "[Empty Content]")

    if doc.links:
        print("\n--- Outbound Hyperlinks Sample ---")
        for l in doc.links[:5]:
            print(f"  * {l.text or '[No Anchor Text]'} -> {l.url}")

    if doc.warnings:
        print("\n--- Extraction Warnings ---")
        for w in doc.warnings:
            print(f"  [!] {w}")


def main():
    parser = argparse.ArgumentParser(
        description="End-to-End OSINT Pipeline: Target -> Queries -> Search -> Fetch -> Extract"
    )
    parser.add_argument("--name", default="Ramesh Kumar", help="Target person's full name")
    parser.add_argument("--location", default="Bhubaneswar", help="Target location")
    parser.add_argument("--org", default="ABC Ltd", help="Target organization")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=["tender", "director"],
        help="Target context keywords",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "wikipedia", "duckduckgo", "searxng", "serpapi", "tavily"],
        default=settings.search_provider,
        help="Search provider backend (default from .env or 'mock')",
    )
    parser.add_argument("--api-key", default=None, help="Provider API key")
    parser.add_argument("--api-url", default=None, help="Custom provider endpoint URL")
    parser.add_argument(
        "--real-fetch",
        action="store_true",
        help="Force real HTTP network fetching instead of mock fetcher",
    )
    parser.add_argument(
        "--direct-url",
        default=None,
        help="Test fetch and extract directly on a specific live URL (skips search discovery)",
    )

    args = parser.parse_args()
    use_real = args.real_fetch or (settings.fetcher_type.lower() == "http")

    asyncio.run(
        run_pipeline(
            name=args.name,
            location=args.location,
            organization=args.org,
            keywords=args.keywords,
            provider_name=args.provider,
            api_key=args.api_key,
            api_url=args.api_url,
            use_real_fetcher=use_real,
            direct_url=args.direct_url,
        )
    )


if __name__ == "__main__":
    main()
