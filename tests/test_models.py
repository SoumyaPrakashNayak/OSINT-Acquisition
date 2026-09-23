"""Test TargetPerson and SearchResult schemas (Phase 0)."""

import pytest
from pydantic import ValidationError

from app.models.schemas import SearchResult, TargetPerson


def test_valid_target_with_name_and_location():
    """Test 0.2: Target with valid name and location succeeds."""
    payload = {
        "name": "Ramesh Kumar",
        "location": "Bhubaneswar",
    }
    target = TargetPerson(**payload)
    assert target.name == "Ramesh Kumar"
    assert target.location == "Bhubaneswar"
    assert target.aliases == []
    assert target.organization is None
    assert target.phone is None
    assert target.username is None
    assert target.keywords == []


def test_missing_name_fails():
    """Test 0.3: Target without name raises ValidationError."""
    payload = {
        "location": "Bhubaneswar",
    }
    with pytest.raises(ValidationError) as exc_info:
        TargetPerson(**payload)
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("name",) for err in errors)


@pytest.mark.parametrize("empty_name", ["", "   ", "\t\n"])
def test_empty_or_whitespace_name_fails(empty_name: str):
    """Test 0.4: Target with empty or whitespace-only name fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        TargetPerson(name=empty_name)
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("name",) for err in errors)


def test_optional_fields_remain_empty_or_none():
    """Test 0.5: Target with only name has defaults for all optional fields."""
    target = TargetPerson(name="Ramesh Kumar")
    assert target.name == "Ramesh Kumar"
    assert target.aliases == []
    assert target.phone is None
    assert target.location is None
    assert target.organization is None
    assert target.username is None
    assert target.keywords == []


def test_whitespace_trimmed_and_empty_list_items_removed():
    """Test string trimming and removal of blank list items."""
    target = TargetPerson(
        name="  Ramesh Kumar  ",
        aliases=["  Ramesh  ", "", "  ", "R. Kumar"],
        location=" Bhubaneswar ",
        organization="  ABC Ltd  ",
        phone="  +919876543210  ",
        username="  rkumar  ",
        keywords=["  fraud  ", "", "scam"],
    )
    assert target.name == "Ramesh Kumar"
    assert target.aliases == ["Ramesh", "R. Kumar"]
    assert target.location == "Bhubaneswar"
    assert target.organization == "ABC Ltd"
    assert target.phone == "+919876543210"
    assert target.username == "rkumar"
    assert target.keywords == ["fraud", "scam"]


def test_empty_optional_strings_become_none():
    """Ensure empty optional strings are sanitized to None."""
    target = TargetPerson(
        name="Ramesh Kumar",
        location="   ",
        organization="",
        phone="",
        username="",
    )
    assert target.location is None
    assert target.organization is None
    assert target.phone is None
    assert target.username is None


def test_search_result_schema_valid():
    """Test SearchResult schema validation with valid URL."""
    result = SearchResult(
        title="Ramesh Kumar joins ABC Ltd",
        url="https://example.com/article",
        source="example.com",
        snippet="Ramesh Kumar has joined ABC Ltd...",
    )
    assert result.title == "Ramesh Kumar joins ABC Ltd"
    assert result.url == "https://example.com/article"
    assert result.source == "example.com"


def test_search_result_invalid_url_fails():
    """Test SearchResult rejects malformed or non-http/https URLs."""
    with pytest.raises(ValidationError):
        SearchResult(
            title="Some Title",
            url="not-a-valid-url",
        )

    with pytest.raises(ValidationError):
        SearchResult(
            title="Some Title",
            url="ftp://example.com/file",
        )
