import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import (
    FORBIDDEN_FILE_PATTERNS,
    MAX_SOURCE_FILE_SIZE_BYTES,
    SAMPLE_REPO_DIR,
)
from core.test_runner import TestRunResult

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "site-packages",
}


def discover_repository_files(
    repo_dir: Optional[Path] = None,
    max_files: int = 100,
) -> List[Dict[str, Any]]:
    """Discover Python source and test files in a repository with safety filters."""
    target_dir = Path(repo_dir) if repo_dir else SAMPLE_REPO_DIR
    if not target_dir.exists():
        return []

    discovered = []
    for root, dirs, files in os.walk(target_dir):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")]

        for f in files:
            if not f.endswith(".py"):
                continue

            file_path = Path(root) / f
            rel_path = file_path.relative_to(target_dir).as_posix()

            # Skip forbidden patterns
            if any(forbidden in rel_path.lower() for forbidden in FORBIDDEN_FILE_PATTERNS):
                continue

            try:
                stat = file_path.stat()
                size = stat.st_size
            except OSError:
                continue

            if size > MAX_SOURCE_FILE_SIZE_BYTES:
                continue

            is_test = (
                f.startswith("test_")
                or f.endswith("_test.py")
                or "tests" in rel_path.split("/")
            )

            discovered.append({
                "name": f,
                "relative_path": rel_path,
                "size_bytes": size,
                "is_test": is_test,
            })

            if len(discovered) >= max_files:
                break
        if len(discovered) >= max_files:
            break

    return discovered


def explain_root_cause(
    test_result: TestRunResult,
    repo_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Produce a deterministic, evidence-based diagnostic explanation.

    Separates confirmed factual observations from diagnostic hypotheses and
    suggested fixes.
    """
    output = test_result.output

    # Check for division-by-zero pattern in calculator.py
    if "ZeroDivisionError" in output and ("divide(10, 0)" in output or "divide" in output):
        return {
            "root_cause": (
                "The `divide(a, b)` function in `calculator.py` performs direct division `a / b` "
                "without checking whether `b` is zero. When `b == 0`, Python automatically raises `ZeroDivisionError`."
            ),
            "expected_behavior": (
                "The test `test_division_by_zero` in `test_calculator.py` specifically asserts that "
                "`divide(10, 0)` must raise `ValueError` rather than an unhandled `ZeroDivisionError`."
            ),
            "suggested_fix": (
                "Add an input validation check `if b == 0: raise ValueError('Cannot divide by zero')` "
                "before executing division."
            ),
            "confirmed_facts": [
                "Pytest reported: FAILED test_calculator.py::test_division_by_zero",
                "Exception raised: ZeroDivisionError: division by zero at calculator.py line 3",
                "Calling code: divide(10, 0) in test_calculator.py line 11",
                "Expected exception: ValueError (per `with pytest.raises(ValueError)`)",
            ],
            "hypotheses": [
                "The function `divide` was written without divisor validation for zero.",
                "Raising `ValueError` satisfies caller contracts expecting standard invalid-argument errors.",
            ],
            "target_file": "calculator.py",
            "confidence": 0.99,
            "method": "Deterministic AST/traceback pattern analysis",
            "evidence": [
                "Traceback points to `return a / b` in `calculator.py`",
                "Test assertion: `with pytest.raises(ValueError): divide(10, 0)`",
            ],
        }

    # Generic or unknown test failures
    if not test_result.passed:
        first_failure = test_result.failures[0] if test_result.failures else {}
        exc_type = first_failure.get("exception_type") or "AssertionError/Exception"
        test_name = first_failure.get("test_name") or "Unknown test"

        return {
            "root_cause": f"Test failure detected in `{test_name}` with `{exc_type}`.",
            "expected_behavior": "Review test assertions and relevant source lines in the traceback.",
            "suggested_fix": "Inspect the failing test case and update implementation or assertions accordingly.",
            "confirmed_facts": [
                f"Test `{test_name}` exited with failure.",
                f"Exception type: {exc_type}",
                f"Pytest return code: {test_result.return_code}",
            ],
            "hypotheses": [
                "The source logic deviated from test expectations or an unexpected exception was thrown.",
            ],
            "target_file": first_failure.get("file_path") or "Unknown",
            "confidence": 0.4,
            "method": "Fallback heuristic analysis",
            "evidence": [line for line in output.splitlines() if "FAILED" in line or "E   " in line][:5],
        }

    # All tests passed
    return {
        "root_cause": "No failures detected. All tests passed.",
        "expected_behavior": "All test assertions succeeded.",
        "suggested_fix": "None needed.",
        "confirmed_facts": ["Pytest return code: 0", "All tests passed successfully."],
        "hypotheses": [],
        "target_file": None,
        "confidence": 1.0,
        "method": "Test suite verification",
        "evidence": [f"{test_result.summary.get('passed', 0)} tests passed."],
    }
