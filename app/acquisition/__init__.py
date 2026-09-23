"""Phase 3: Web Content Acquisition package."""

from app.acquisition.fetcher import HttpWebFetcher, WebFetcher
from app.acquisition.mock_fetcher import MockWebFetcher
from app.acquisition.models import (
    AcquisitionBatchResponse,
    AcquisitionError,
    BatchFetchItem,
    BatchFetchRequest,
    FetchMetadata,
    FetchRequest,
    FetchResult,
    WebDocument,
)
from app.acquisition.service import AcquisitionService
from app.acquisition.url_policy import validate_url_policy

__all__ = [
    "WebFetcher",
    "HttpWebFetcher",
    "MockWebFetcher",
    "AcquisitionService",
    "WebDocument",
    "FetchMetadata",
    "AcquisitionError",
    "FetchResult",
    "FetchRequest",
    "BatchFetchRequest",
    "BatchFetchItem",
    "AcquisitionBatchResponse",
    "validate_url_policy",
]
