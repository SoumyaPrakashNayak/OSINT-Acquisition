"""Tests for deterministic QueryGenerator (Phase 1)."""

import pytest
from app.discovery.query_generator import QueryGenerator
from app.models.schemas import TargetPerson


@pytest.fixture
def generator() -> QueryGenerator:
    return QueryGenerator()


def test_name_only_query(generator: QueryGenerator):
    """Test 1.1: Name-only target generates exact quoted name query."""
    target = TargetPerson(name="Ramesh Kumar")
    queries = generator.generate(target)
    assert queries == ['"Ramesh Kumar"']


def test_name_and_location_queries(generator: QueryGenerator):
    """Test 1.2: Name + location generates exact name and location contextual query."""
    target = TargetPerson(name="Ramesh Kumar", location="Bhubaneswar")
    queries = generator.generate(target)
    assert '"Ramesh Kumar"' in queries
    assert '"Ramesh Kumar" Bhubaneswar' in queries
    # Assert priority order: exact name first, then location
    assert queries.index('"Ramesh Kumar"') < queries.index('"Ramesh Kumar" Bhubaneswar')


def test_name_and_organization_queries(generator: QueryGenerator):
    """Test 1.3: Name + organization generates contextual query."""
    target = TargetPerson(name="Ramesh Kumar", organization="ABC Ltd")
    queries = generator.generate(target)
    assert '"Ramesh Kumar"' in queries
    assert '"Ramesh Kumar" "ABC Ltd"' in queries
    assert queries.index('"Ramesh Kumar"') < queries.index('"Ramesh Kumar" "ABC Ltd"')


def test_alias_queries(generator: QueryGenerator):
    """Test 1.4: Alias generates standalone and contextual alias queries."""
    target = TargetPerson(
        name="Ramesh Kumar",
        aliases=["Ramesh"],
        location="Bhubaneswar",
        organization="ABC Ltd",
    )
    queries = generator.generate(target)
    assert '"Ramesh"' in queries
    assert '"Ramesh" Bhubaneswar' in queries
    assert '"Ramesh" "ABC Ltd"' in queries


def test_duplicate_queries_removed(generator: QueryGenerator):
    """Test 1.5: Duplicate queries are deduplicated while preserving order."""
    # Target having alias identical to name or overlapping entries
    target = TargetPerson(
        name="Ramesh Kumar",
        aliases=["Ramesh Kumar", "Ramesh"],
        location="Bhubaneswar",
    )
    queries = generator.generate(target)
    # Check that each query is unique
    assert len(queries) == len(set(queries))
    # Count of exact query must be 1
    assert queries.count('"Ramesh Kumar"') == 1
    assert queries.count('"Ramesh Kumar" Bhubaneswar') == 1


def test_determinism_identical_runs(generator: QueryGenerator):
    """Test 1.6: Repeated generation on same target produces identical output and order."""
    target = TargetPerson(
        name="Ramesh Kumar",
        aliases=["Ramesh", "R. Kumar"],
        location="Bhubaneswar",
        organization="ABC Ltd",
        username="rkumar99",
        phone="+919876543210",
        keywords=["fraud", "director"],
    )
    run_1 = generator.generate(target)
    run_2 = generator.generate(target)
    assert run_1 == run_2


def test_whitespace_normalization_in_queries(generator: QueryGenerator):
    """Test that extra internal and edge whitespace is normalized."""
    target = TargetPerson(
        name="  Ramesh   Kumar  ",
        location="   Bhubaneswar   ",
    )
    queries = generator.generate(target)
    assert queries[0] == '"Ramesh Kumar"'
    assert queries[1] == '"Ramesh Kumar" Bhubaneswar'
    assert not any("  " in q for q in queries)


def test_full_context_generation(generator: QueryGenerator):
    """Test generation with all fields provided."""
    target = TargetPerson(
        name="Ramesh Kumar",
        aliases=["Ramesh"],
        location="Bhubaneswar",
        organization="ABC Ltd",
    )
    queries = generator.generate(target)
    expected_subset = [
        '"Ramesh Kumar"',
        '"Ramesh Kumar" Bhubaneswar',
        '"Ramesh Kumar" "ABC Ltd"',
        '"Ramesh Kumar" Bhubaneswar "ABC Ltd"',
        '"Ramesh"',
        '"Ramesh" Bhubaneswar',
        '"Ramesh" "ABC Ltd"',
        '"Ramesh" Bhubaneswar "ABC Ltd"',
    ]
    for expected in expected_subset:
        assert expected in queries
