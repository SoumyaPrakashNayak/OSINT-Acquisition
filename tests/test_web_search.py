"""Tests for SearchProvider abstraction, MockSearchProvider, and DiscoveryService (Phase 2)."""

import pytest
from app.discovery.mock_provider import MockSearchProvider
from app.discovery.query_generator import QueryGenerator
from app.discovery.service import DiscoveryService
from app.models.schemas import SearchResult, TargetPerson


@pytest.mark.asyncio
async def test_mock_search_deterministic():
    """Test 2.1: MockSearchProvider returns deterministic results for given query."""
    provider = MockSearchProvider()
    query = '"Ramesh Kumar" Bhubaneswar'
    results = await provider.search(query, limit=5)

    assert len(results) >= 1
    assert "ramesh" in results[0].url.lower()
    # Repeating search returns identical results
    results_repeat = await provider.search(query, limit=5)
    assert results == results_repeat


@pytest.mark.asyncio
async def test_search_result_schema():
    """Test 2.2: Search result contains title and url at minimum, and valid fields."""
    provider = MockSearchProvider()
    results = await provider.search('"Ramesh Kumar"')

    for res in results:
        assert isinstance(res.title, str)
        assert len(res.title.strip()) > 0
        assert isinstance(res.url, str)
        assert res.url.startswith("http://") or res.url.startswith("https://")
        assert res.source is not None


@pytest.mark.asyncio
async def test_result_deduplication():
    """Test 2.5: Duplicate URLs across different queries are deduplicated (A, A, B -> A, B)."""
    # Create mock provider returning overlapping results
    item_a = SearchResult(
        title="Article A",
        url="https://example.com/article-a?utm_source=news",
        source="example.com",
        snippet="Snippet A",
    )
    item_a_duplicate = SearchResult(
        title="Article A Duplicate",
        url="https://example.com/article-a",
        source="example.com",
        snippet="Snippet A duplicate",
    )
    item_b = SearchResult(
        title="Article B",
        url="https://example.com/article-b",
        source="example.com",
        snippet="Snippet B",
    )

    provider = MockSearchProvider(
        custom_results={
            "query_1": [item_a, item_b],
            "query_2": [item_a_duplicate],
        }
    )

    class FixedQueryGenerator(QueryGenerator):
        def generate(self, target: TargetPerson) -> list[str]:
            return ["query_1", "query_2"]

    service = DiscoveryService(
        query_generator=FixedQueryGenerator(),
        search_provider=provider,
    )
    target = TargetPerson(name="Ramesh Kumar")
    response = await service.discover(target)

    # Normalized URLs should collapse item_a and item_a_duplicate
    assert response.total_results == 2
    urls = [r.url for r in response.results]
    assert urls == ["https://example.com/article-a", "https://example.com/article-b"]


@pytest.mark.asyncio
async def test_multiple_queries_execution():
    """Test 2.6: DiscoveryService executes multiple queries and aggregates results."""
    provider = MockSearchProvider()
    service = DiscoveryService(
        query_generator=QueryGenerator(),
        search_provider=provider,
    )
    target = TargetPerson(
        name="Ramesh Kumar",
        location="Bhubaneswar",
        organization="ABC Ltd",
    )
    response = await service.discover(target)

    assert len(response.queries) >= 3
    assert '"Ramesh Kumar"' in response.queries
    assert '"Ramesh Kumar" Bhubaneswar' in response.queries
    assert '"Ramesh Kumar" "ABC Ltd"' in response.queries
    assert response.total_results > 0
    assert len(response.results) == response.total_results


@pytest.mark.asyncio
async def test_provider_failure_tolerance():
    """Test 2.7: Partial provider failures (Query 1 success, Query 2 fail, Query 3 success) do not crash pipeline."""
    failing_query = '"Ramesh Kumar" Bhubaneswar'
    provider = MockSearchProvider(failing_queries={failing_query})

    service = DiscoveryService(
        query_generator=QueryGenerator(),
        search_provider=provider,
    )
    target = TargetPerson(
        name="Ramesh Kumar",
        location="Bhubaneswar",
        organization="ABC Ltd",
    )

    # Should not raise exception
    response = await service.discover(target)

    # Successful results still gathered
    assert response.total_results > 0
    # Warning recorded for failing query
    assert len(response.warnings) == 1
    assert response.warnings[0]["query"] == failing_query
    assert "Simulated search provider failure" in response.warnings[0]["error"]
