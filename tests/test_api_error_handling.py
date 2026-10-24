import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_404_not_found(client):
    """Verify that unknown routes return structured JSON with 404."""
    response = client.get("/api/nonexistent_route")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert "not found" in data["message"].lower()


def test_405_method_not_allowed(client):
    """Verify that using the wrong HTTP verb returns structured JSON with 405."""
    # GET on POST-only endpoint
    response = client.get("/api/patch/apply")
    assert response.status_code == 405
    data = response.get_json()
    assert data["status"] == "error"


def test_malformed_patch_target(client):
    """Verify that bad patch targets return HTTP 400 error."""
    response = client.post("/api/patch/apply", json={"file_path": "../escape.py"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "traversal" in data["message"].lower() or "invalid" in data["message"].lower()


def test_empty_content_memory_save(client):
    """Verify that empty memory saves return HTTP 400."""
    response = client.post("/api/memory/save", json={"content": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
