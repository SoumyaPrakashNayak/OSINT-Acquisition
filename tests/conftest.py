"""Pytest configuration and global fixtures for OSINT Intelligence Component."""

import pytest
from app.api.routes import get_search_provider
from app.discovery.mock_provider import MockSearchProvider
from app.main import app


@pytest.fixture(autouse=True)
def override_test_providers():
    """Ensure automated API tests run 100% offline and deterministically with MockSearchProvider."""
    app.dependency_overrides[get_search_provider] = lambda: MockSearchProvider()
    yield
    app.dependency_overrides.pop(get_search_provider, None)
