import pytest
from app import app
from core.patching import reset_sample_repository


@pytest.fixture
def client():
    app.config["TESTING"] = True
    # Ensure baseline bug is active
    reset_sample_repository()
    with app.test_client() as client:
        yield client


def test_baseline_failure_detection(client):
    """Verify that diagnosis accurately detects the intentional ZeroDivisionError."""
    response = client.post("/api/diagnose")
    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "success"
    assert data["tests_passed"] is False
    assert data["return_code"] != 0
    assert "ZeroDivisionError" in data["output"]

    # Verify structured failure details
    assert len(data["failures"]) >= 1
    failure = data["failures"][0]
    assert failure["test_name"] == "test_division_by_zero"
    assert failure["exception_type"] == "ZeroDivisionError"


def test_root_cause_explanation_separation(client):
    """Verify that confirmed facts are strictly separated from hypotheses and fixes."""
    response = client.post("/api/diagnose")
    data = response.get_json()
    root_cause = data["root_cause"]

    assert "ZeroDivisionError" in root_cause["root_cause"]
    assert "ValueError" in root_cause["expected_behavior"]

    # Confirmed facts must be non-empty list of verified findings
    assert isinstance(root_cause["confirmed_facts"], list)
    assert len(root_cause["confirmed_facts"]) > 0
    assert any("ZeroDivisionError" in fact for fact in root_cause["confirmed_facts"])

    # Hypotheses must provide actionable reasoning
    assert isinstance(root_cause["hypotheses"], list)
    assert len(root_cause["hypotheses"]) > 0
    assert "calculator.py" in root_cause["target_file"]
    assert root_cause["confidence"] > 0.8
