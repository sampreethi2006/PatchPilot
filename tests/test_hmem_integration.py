import pytest
from app import app
from core.hmem import is_hmem_ready, run_hmem, save_finding, search_findings


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_hmem_readiness():
    """Verify that H-MEM binaries and scripts are detected on the host."""
    ready, error_msg = is_hmem_ready()
    assert ready is True, f"H-MEM components not ready: {error_msg}"


def test_hmem_save_and_search():
    """Verify that H-MEM TypeScript bridge saves and retrieves working memory."""
    test_content = "PatchPilot test memory entry for verification of H-MEM retrieval"
    save_result = save_finding(
        content=test_content,
        source="tests/test_hmem_integration.py",
        confidence=0.95,
        tags=["test:unit", "language:python"],
    )
    assert save_result.get("ok") is True
    assert "id" in save_result

    # Search for stored finding
    search_result = search_findings("verification of H-MEM retrieval")
    assert search_result.get("ok") is True
    assert "memories" in search_result
    assert len(search_result["memories"]) > 0


def test_hmem_invalid_action_graceful_error():
    """Ensure invalid H-MEM actions raise proper Python exceptions."""
    with pytest.raises(RuntimeError):
        run_hmem("invalid_action_xyz")


def test_memory_search_endpoint(client):
    """Verify /api/memory/search endpoint contract."""
    response = client.post("/api/memory/search", json={"query": "ZeroDivisionError"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "results" in data
    assert "memories" in data["results"]
