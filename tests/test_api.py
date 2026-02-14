"""
API endpoint tests for NFL RAG App.

Tests both RAG and Agent endpoints.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    from src.api.main import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """Tests for health and info endpoints."""

    def test_root_endpoint(self, client):
        """Root endpoint should return API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "NFL" in data["name"]

    def test_health_endpoint(self, client):
        """Health endpoint should return status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "vector_store" in data
        assert "llm" in data
        assert "agent" in data

    def test_stats_endpoint(self, client):
        """Stats endpoint should return statistics."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "chunk_count" in data
        assert data["chunk_count"] > 0

    def test_teams_endpoint(self, client):
        """Teams endpoint should return team list."""
        response = client.get("/teams")
        assert response.status_code == 200
        data = response.json()
        assert "AFC East" in data
        assert "KC" in data["AFC West"]


class TestAgentEndpoint:
    """Tests for the agent endpoint."""

    def test_agent_get_request(self, client):
        """Agent GET request should work."""
        response = client.get("/agent?q=How+many+teams+are+in+the+NFL")
        # May be 200 or 503 depending on Ollama availability
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "tool_calls" in data
            assert "total_time_ms" in data

    def test_agent_post_request(self, client):
        """Agent POST request should work."""
        response = client.post(
            "/agent",
            json={"question": "Who led the NFL in passing yards in 2024?"}
        )
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "tool_calls" in data
            assert "model" in data

    def test_agent_invalid_request(self, client):
        """Agent should reject invalid requests."""
        # Empty question
        response = client.post("/agent", json={"question": ""})
        assert response.status_code == 422  # Validation error

    def test_agent_response_structure(self, client):
        """Agent response should have correct structure."""
        response = client.get("/agent?q=Test+question")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data["answer"], str)
            assert isinstance(data["tool_calls"], list)
            assert isinstance(data["thinking"], list)
            assert isinstance(data["iterations"], int)
            assert isinstance(data["total_time_ms"], (int, float))


class TestRAGEndpoint:
    """Tests for the RAG query endpoint."""

    def test_query_get_request(self, client):
        """Query GET request should work."""
        response = client.get("/query?q=Tell+me+about+the+Chiefs")
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data

    def test_query_post_request(self, client):
        """Query POST request should work."""
        response = client.post(
            "/query",
            json={
                "query": "Tell me about Patrick Mahomes",
                "num_results": 3,
                "temperature": 0.5,
            }
        )
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert len(data["sources"]) <= 3


class TestSearchEndpoint:
    """Tests for the search endpoint (no LLM generation)."""

    def test_search_get_request(self, client):
        """Search GET request should work."""
        response = client.get("/search?q=Mahomes+touchdown")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert "time_ms" in data

    def test_search_with_filters(self, client):
        """Search with filters should work."""
        response = client.get("/search?q=playoff&team=KC&n=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5

    def test_search_returns_metadata(self, client):
        """Search results should include metadata."""
        response = client.get("/search?q=quarterback&n=3")
        assert response.status_code == 200
        data = response.json()

        if data["results"]:
            result = data["results"][0]
            assert "chunk_id" in result
            assert "score" in result
            assert "preview" in result
            assert "metadata" in result


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_for_unknown_endpoint(self, client):
        """Unknown endpoints should return 404."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_invalid_chunk_id(self, client):
        """Invalid chunk ID should return 404."""
        response = client.get("/chunks/nonexistent_chunk_id_12345")
        assert response.status_code == 404

    def test_validation_errors(self, client):
        """Invalid input should return validation errors."""
        # n_results out of range
        response = client.get("/search?q=test&n=100")
        assert response.status_code == 422
