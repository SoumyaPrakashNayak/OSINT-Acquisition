"""FastAPI route definitions for OSINT Intelligence Component."""

from fastapi import APIRouter, Depends, Request

from app.acquisition.fetcher import HttpWebFetcher, WebFetcher
from app.acquisition.mock_fetcher import MockWebFetcher
from app.acquisition.models import (
    AcquisitionBatchResponse,
    BatchFetchRequest,
    FetchRequest,
    FetchResult,
)
from app.acquisition.service import AcquisitionService
from app.extraction.models import ExtractionRequest, ExtractionResult
from app.extraction.service import ExtractionService
from app.config import settings
from app.discovery.mock_provider import MockSearchProvider
from app.discovery.provider import SearchProvider
from app.discovery.query_generator import QueryGenerator
from app.discovery.service import DiscoveryService
from app.models.schemas import DiscoveryResponse, TargetPerson

router = APIRouter()


def get_search_provider() -> SearchProvider:
    """Dependency provider returning active SearchProvider based on application settings."""
    provider_type = (settings.search_provider or "mock").lower()
    if provider_type == "mock":
        return MockSearchProvider()

    # For real external providers, delegate to http_provider if available
    try:
        from app.discovery.http_provider import HttpSearchProvider
        return HttpSearchProvider(
            provider_type=provider_type,
            api_key=settings.search_api_key,
            api_url=settings.search_api_url,
            timeout=settings.search_timeout_seconds,
        )
    except Exception:
        # Fallback to mock if real provider cannot initialize
        return MockSearchProvider()


def get_discovery_service(
    provider: SearchProvider = Depends(get_search_provider),
) -> DiscoveryService:
    """Dependency provider returning DiscoveryService with injected dependencies."""
    return DiscoveryService(
        query_generator=QueryGenerator(),
        search_provider=provider,
        max_results_per_query=settings.max_results_per_query,
    )


@router.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns operational status without depending on external APIs.
    """
    return {"status": "ok"}


@router.post("/osint/discover", response_model=DiscoveryResponse, tags=["OSINT Discovery"])
async def discover_target(
    target: TargetPerson,
    request: Request,
    discovery_service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryResponse:
    """Execute OSINT discovery for a target person.

    Generates search queries, executes discovery against configured provider,
    normalizes and deduplicates candidate results.
    """
    investigation_id = getattr(request.state, "request_id", None)
    return await discovery_service.discover(target, investigation_id=investigation_id)


# --- Phase 3: Web Content Acquisition Dependencies & Routes ---

def get_web_fetcher() -> WebFetcher:
    """Dependency provider returning active WebFetcher based on settings."""
    fetcher_type = (getattr(settings, "fetcher_type", "mock") or "mock").lower()
    if fetcher_type == "http":
        return HttpWebFetcher(
            timeout=settings.fetch_timeout_seconds,
            max_response_size_mb=settings.max_response_size_mb,
            max_redirects=settings.max_redirects,
            user_agent=settings.fetch_user_agent,
        )
    return MockWebFetcher(max_redirects=settings.max_redirects)


def get_acquisition_service(
    fetcher: WebFetcher = Depends(get_web_fetcher),
) -> AcquisitionService:
    """Dependency provider returning AcquisitionService."""
    return AcquisitionService(
        fetcher=fetcher,
        max_concurrent_fetches=settings.max_concurrent_fetches,
    )


@router.post("/osint/fetch", response_model=FetchResult, tags=["OSINT Acquisition"])
async def fetch_url(
    payload: FetchRequest,
    acquisition_service: AcquisitionService = Depends(get_acquisition_service),
) -> FetchResult:
    """Fetch raw web content for a single candidate URL (Phase 3).

    Returns a structured FetchResult (success with WebDocument, or controlled failure with AcquisitionError).
    """
    return await acquisition_service.acquire(payload.url)


@router.post(
    "/osint/fetch-batch",
    response_model=AcquisitionBatchResponse,
    tags=["OSINT Acquisition"],
)
async def fetch_urls_batch(
    payload: BatchFetchRequest,
    acquisition_service: AcquisitionService = Depends(get_acquisition_service),
) -> AcquisitionBatchResponse:
    """Fetch raw web content for multiple candidate URLs concurrently (Phase 3)."""
    return await acquisition_service.acquire_many(payload.urls)


# --- Phase 4: Web Content Extraction Dependencies & Routes ---

def get_extraction_service() -> ExtractionService:
    """Dependency provider returning ExtractionService."""
    return ExtractionService()


@router.post("/osint/extract", response_model=ExtractionResult, tags=["OSINT Extraction"])
async def extract_content(
    payload: ExtractionRequest,
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResult:
    """Extract structured text, metadata, and quality metrics from an acquired WebDocument (Phase 4)."""
    return extraction_service.extract(payload.web_document)
