import difflib
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.config import FORBIDDEN_FILE_PATTERNS, SAMPLE_REPO_DIR
from core.test_runner import TestRunResult, run_repository_tests

logger = logging.getLogger("patchpilot.patching")

# Pristine intentional bug version of calculator.py for reset & baseline
PRISTINE_CALCULATOR_CODE = """def divide(a, b):
    # Intentional bug: does not handle division by zero
    return a / b
"""

# Fixed version of calculator.py that satisfies test_calculator.py
FIXED_CALCULATOR_CODE = """def divide(a, b):
    # Fixed: validate divisor before dividing
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b
"""

PRISTINE_TEST_CALCULATOR_CODE = """import pytest
from calculator import divide


def test_normal_division():
    assert divide(10, 2) == 5


def test_division_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)
"""


def validate_relative_path(repo_dir: Path, rel_path: str) -> Tuple[bool, Optional[str], Optional[Path]]:
    """Validate that a relative path is safely within the target repository."""
    if not rel_path or not rel_path.strip():
        return False, "Target file path is empty.", None

    clean_path = rel_path.strip().replace("\\", "/")

    # Check for path traversal attempts
    parts = clean_path.split("/")
    if ".." in parts or clean_path.startswith("/") or ":" in clean_path:
        return False, f"Path traversal detected in path: {rel_path}", None

    for forbidden in FORBIDDEN_FILE_PATTERNS:
        if forbidden in clean_path.lower():
            return False, f"Modifications to protected file pattern '{forbidden}' are forbidden.", None

    resolved_path = (repo_dir / clean_path).resolve()
    resolved_repo = repo_dir.resolve()

    # Ensure resolved path is strictly within repo directory
    try:
        resolved_path.relative_to(resolved_repo)
    except ValueError:
        return False, f"Resolved path '{resolved_path}' is outside repository root '{resolved_repo}'", None

    return True, None, resolved_path


def generate_unified_diff(
    original_text: str,
    patched_text: str,
    from_file: str = "a/calculator.py",
    to_file: str = "b/calculator.py",
) -> str:
    """Generate a clean unified diff string between original and patched code."""
    orig_lines = original_text.splitlines(keepends=True)
    patch_lines = patched_text.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            patch_lines,
            fromfile=from_file,
            tofile=to_file,
            lineterm="\n",
        )
    )
    return "".join(diff_lines)


def propose_patch_for_calculator(repo_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate a proposed minimal fix for the division by zero bug."""
    target_repo = Path(repo_dir) if repo_dir else SAMPLE_REPO_DIR
    target_file = target_repo / "calculator.py"

    if target_file.exists():
        original_code = target_file.read_text(encoding="utf-8")
    else:
        original_code = PRISTINE_CALCULATOR_CODE

    patched_code = FIXED_CALCULATOR_CODE
    diff = generate_unified_diff(
        original_code,
        patched_code,
        from_file="a/calculator.py",
        to_file="b/calculator.py",
    )

    return {
        "file_path": "calculator.py",
        "description": "Add divisor validation to raise ValueError when b == 0.",
        "original_code": original_code,
        "patched_code": patched_code,
        "unified_diff": diff,
        "safe_to_apply": True,
    }


def apply_patch(
    repo_dir: Optional[Path] = None,
    file_rel_path: str = "calculator.py",
    patched_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a validated patch to a file in the repository and run verification."""
    target_repo = Path(repo_dir) if repo_dir else SAMPLE_REPO_DIR
    is_valid, err_msg, file_path = validate_relative_path(target_repo, file_rel_path)

    if not is_valid or file_path is None:
        return {
            "success": False,
            "error": err_msg or "Invalid patch target.",
            "verified": False,
        }

    # Backup existing file before editing
    backup_path = file_path.with_suffix(file_path.suffix + ".orig.bak")
    original_code = ""
    if file_path.exists():
        original_code = file_path.read_text(encoding="utf-8")
        shutil.copyfile(file_path, backup_path)

    code_to_write = patched_code if patched_code is not None else FIXED_CALCULATOR_CODE

    # Write patched code safely
    file_path.write_text(code_to_write, encoding="utf-8")

    diff = generate_unified_diff(
        original_code,
        code_to_write,
        from_file=f"a/{file_rel_path}",
        to_file=f"b/{file_rel_path}",
    )

    # Run verification test run immediately
    verification_run: TestRunResult = run_repository_tests(target_repo)

    return {
        "success": True,
        "file_path": file_rel_path,
        "backup_path": str(backup_path),
        "unified_diff": diff,
        "verified": verification_run.passed,
        "test_run": verification_run.to_dict(),
        "message": (
            "Patch successfully applied and verified by test suite."
            if verification_run.passed
            else "Patch applied, but verification tests failed or reported regressions."
        ),
    }


def reset_sample_repository(repo_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Restore the sample repository to its pristine, intentionally failing state."""
    target_repo = Path(repo_dir) if repo_dir else SAMPLE_REPO_DIR
    calc_path = target_repo / "calculator.py"
    test_calc_path = target_repo / "test_calculator.py"

    target_repo.mkdir(parents=True, exist_ok=True)
    calc_path.write_text(PRISTINE_CALCULATOR_CODE, encoding="utf-8")
    test_calc_path.write_text(PRISTINE_TEST_CALCULATOR_CODE, encoding="utf-8")

    # Clean up any leftover .bak files
    for bak in target_repo.glob("*.bak"):
        try:
            bak.unlink()
        except OSError:
            pass

    # Verify baseline failure is present
    baseline_run = run_repository_tests(target_repo)

    return {
        "reset": True,
        "message": "Sample repository reset to pristine baseline with intentional division-by-zero bug.",
        "baseline_test_passed": baseline_run.passed,
        "baseline_failing_as_expected": (not baseline_run.passed),
    }
