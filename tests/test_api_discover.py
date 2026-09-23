"""End-to-end integration tests for POST /osint/discover (Phase 2)."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_end_to_end_discovery():
    """Test 2.8: Complete pipeline flow from HTTP request to discovery response."""
    payload = {
        "name": "Ramesh Kumar",
        "aliases": ["Ramesh"],
        "location": "Bhubaneswar",
        "organization": "ABC Ltd",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/discover", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "target" in data
        assert data["target"]["name"] == "Ramesh Kumar"
        assert data["target"]["location"] == "Bhubaneswar"
        assert data["target"]["organization"] == "ABC Ltd"

        assert "queries" in data
        assert len(data["queries"]) >= 4
        assert '"Ramesh Kumar"' in data["queries"]

        assert "results" in data
        assert data["total_results"] == len(data["results"])
        assert data["total_results"] > 0

        # Validate structure of candidate results
        first_result = data["results"][0]
        assert "title" in first_result
        assert "url" in first_result
        assert "source" in first_result
        assert first_result["url"].startswith("http")


@pytest.mark.asyncio
async def test_discovery_invalid_target_structured_error():
    """Test POST /osint/discover returns structured error when target is invalid."""
    invalid_payload = {
        "name": "   ",
        "location": "Bhubaneswar",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/discover", json=invalid_payload)
        assert response.status_code == 422

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_TARGET"
        assert "name" in data["error"]["message"]


@pytest.mark.asyncio
async def test_discovery_name_only_target():
    """Test POST /osint/discover works with target that only has a name."""
    payload = {"name": "Ramesh Kumar"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/osint/discover", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["target"]["name"] == "Ramesh Kumar"
        assert data["queries"] == ['"Ramesh Kumar"']
        assert data["total_results"] >= 1
