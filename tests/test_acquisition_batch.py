"""Tests for batch acquisition orchestration and concurrency controls."""

import pytest
from app.acquisition.errors import FETCH_TIMEOUT, HTTP_FORBIDDEN, HTTP_NOT_FOUND
from app.acquisition.mock_fetcher import MockWebFetcher
from app.acquisition.service import AcquisitionService


@pytest.mark.asyncio
async def test_batch_all_successful():
    """Test 3.6.1: Batch of multiple accessible URLs succeeds completely."""
    fetcher = MockWebFetcher()
    urls = [
        "https://example.com/item-1",
        "https://example.com/item-2",
        "https://example.com/item-3",
    ]
    service = AcquisitionService(fetcher=fetcher, max_concurrent_fetches=3)
    response = await service.acquire_many(urls)

    assert response.total == 3
    assert response.successful == 3
    assert response.failed == 0
    assert len(response.results) == 3
    for r in response.results:
        assert r.success is True
        assert r.document is not None
        assert r.error is None


@pytest.mark.asyncio
async def test_batch_partial_failure():
    """Test 3.6.2: A failure in item B does not fail A and C."""
    fetcher = MockWebFetcher()
    url_a = "https://example.com/a"
    url_b = "https://example.com/b"
    url_c = "https://example.com/c"

    fetcher.add_response(url_a, status_code=200)
    fetcher.add_response(url_b, status_code=404)
    fetcher.add_response(url_c, status_code=200)

    service = AcquisitionService(fetcher=fetcher)
    response = await service.acquire_many([url_a, url_b, url_c])

    assert response.total == 3
    assert response.successful == 2
    assert response.failed == 1

    item_map = {r.url: r for r in response.results}
    assert item_map[url_a].success is True
    assert item_map[url_c].success is True
    assert item_map[url_b].success is False
    assert item_map[url_b].error is not None
    assert item_map[url_b].error.code == HTTP_NOT_FOUND


@pytest.mark.asyncio
async def test_batch_mixed_failure_types():
    """Test 3.6.3: Different failures (404, timeout, 403) retain their individual error codes."""
    fetcher = MockWebFetcher()
    url_200 = "https://example.com/ok"
    url_404 = "https://example.com/missing"
    url_timeout = "https://example.com/timeout"
    url_403 = "https://example.com/forbidden"

    fetcher.add_response(url_200, status_code=200)
    fetcher.add_response(url_404, status_code=404)
    fetcher.add_error(url_timeout, code=FETCH_TIMEOUT, message="Timeout", retryable=True)
    fetcher.add_response(url_403, status_code=403)

    service = AcquisitionService(fetcher=fetcher)
    response = await service.acquire_many([url_200, url_404, url_timeout, url_403])

    assert response.total == 4
    assert response.successful == 1
    assert response.failed == 3

    item_map = {r.url: r for r in response.results}
    assert item_map[url_200].success is True
    assert item_map[url_404].error.code == HTTP_NOT_FOUND
    assert item_map[url_timeout].error.code == FETCH_TIMEOUT
    assert item_map[url_403].error.code == HTTP_FORBIDDEN


@pytest.mark.asyncio
async def test_batch_concurrency_limit():
    """Test 3.6.4: Concurrency limit is strictly respected via semaphore."""
    fetcher = MockWebFetcher(delay=0.01)
    urls = [f"https://example.com/item-{i}" for i in range(10)]
    service = AcquisitionService(fetcher=fetcher, max_concurrent_fetches=3)

    response = await service.acquire_many(urls)
    assert response.total == 10
    assert response.successful == 10
    # Peak observed concurrency in mock fetcher must not exceed configured limit of 3
    assert fetcher._max_observed_concurrency <= 3
