import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_dashboard_route_returns_200(client):
    """Verify that the dashboard is served through Flask rather than direct file access."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"PatchPilot AI" in response.data
    assert b"Autonomous Bug Investigation" in response.data or b"Autonomous Software Repair" in response.data


def test_health_endpoint_truthful_contract(client):
    """Verify that /api/health returns truthful system metrics without faking."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "ok"
    assert data["app"] == "PatchPilot AI"
    assert "environment" in data
    assert "python_version" in data["environment"]
    assert "python_executable" in data["environment"]
    assert "hmem" in data
    assert "ready" in data["hmem"]
    assert "sample_repository" in data
    assert data["sample_repository"]["exists"] is True
    assert "ai_provider" in data


def test_repo_files_endpoint(client):
    """Verify that /api/repo/files filters out hidden/cache directories."""
    response = client.get("/api/repo/files")
    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "success"
    filenames = [f["name"] for f in data["files"]]
    assert "calculator.py" in filenames
    assert "test_calculator.py" in filenames
    # Verify virtualenv and cache files are excluded
    assert not any(".pytest_cache" in f["relative_path"] for f in data["files"])
    assert not any("__pycache__" in f["relative_path"] for f in data["files"])
