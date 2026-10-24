import pytest
from app import app
from core.config import SAMPLE_REPO_DIR
from core.patching import (
    apply_patch,
    propose_patch_for_calculator,
    reset_sample_repository,
    validate_relative_path,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    reset_sample_repository()
    with app.test_client() as client:
        yield client


def test_patch_proposal_structure():
    """Verify that patch proposal contains valid unified diff."""
    proposal = propose_patch_for_calculator(SAMPLE_REPO_DIR)
    assert proposal["file_path"] == "calculator.py"
    assert "unified_diff" in proposal
    diff = proposal["unified_diff"]
    assert "--- a/calculator.py" in diff
    assert "+++ b/calculator.py" in diff
    assert "+        raise ValueError" in diff or "+    if b == 0:" in diff


def test_path_traversal_rejection():
    """Ensure malicious paths are rejected to prevent directory traversal."""
    traversal_paths = [
        "../outside.py",
        "../../etc/passwd",
        r"..\..\windows\system32\cmd.exe",
        "/absolute/path/file.py",
        "C:\\Windows\\system.ini",
    ]
    for path in traversal_paths:
        is_valid, err_msg, target_path = validate_relative_path(SAMPLE_REPO_DIR, path)
        assert is_valid is False
        assert target_path is None
        assert "traversal" in err_msg.lower() or "outside" in err_msg.lower()


def test_protected_file_rejection():
    """Ensure sensitive files like .env or credentials cannot be targeted."""
    protected_paths = [
        ".env",
        "subfolder/.env",
        "credentials.json",
        "api_secrets.py",
    ]
    for path in protected_paths:
        is_valid, err_msg, target_path = validate_relative_path(SAMPLE_REPO_DIR, path)
        assert is_valid is False
        assert "forbidden" in err_msg.lower() or "protected" in err_msg.lower()


def test_patch_application_and_verification(client):
    """Verify end-to-end patch application, test execution, and resolution."""
    # 1. Baseline is failing
    res_before = client.post("/api/diagnose")
    assert res_before.get_json()["tests_passed"] is False

    # 2. Apply patch
    res_apply = client.post("/api/patch/apply", json={"file_path": "calculator.py"})
    assert res_apply.status_code == 200
    apply_data = res_apply.get_json()
    assert apply_data["status"] == "success"
    assert apply_data["patch_result"]["verified"] is True

    # 3. Subsequent diagnosis must report all tests passing
    res_after = client.post("/api/diagnose")
    assert res_after.get_json()["tests_passed"] is True

    # 4. Reset sample repo and verify baseline failure is restored
    res_reset = client.post("/api/repo/reset")
    assert res_reset.status_code == 200
    res_post_reset = client.post("/api/diagnose")
    assert res_post_reset.get_json()["tests_passed"] is False
