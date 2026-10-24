import logging
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import MAX_OUTPUT_CHARS, MAX_TEST_TIMEOUT_SEC, PYTHON_EXE, SAMPLE_REPO_DIR

logger = logging.getLogger("patchpilot.test_runner")


@dataclass
class FailureDetail:
    test_name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    exception_type: Optional[str] = None
    message: Optional[str] = None


@dataclass
class TestRunResult:
    passed: bool
    return_code: int
    output: str
    stdout: str
    stderr: str
    duration_sec: float
    failures: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_pytest_failures(stdout: str) -> List[FailureDetail]:
    """Extract structured failure details from pytest stdout."""
    failures = []
    seen_tests = set()

    # 1. Match failure block headers like:
    # ____________________________ test_division_by_zero ____________________________
    failure_blocks = re.split(r"_{5,}\s*([a-zA-Z0-9_]+(?:\[.*?\])?)\s*_{5,}", stdout)

    if len(failure_blocks) > 1:
        for i in range(1, len(failure_blocks), 2):
            test_name = failure_blocks[i].strip()
            block_text = failure_blocks[i + 1] if i + 1 < len(failure_blocks) else ""

            file_match = re.search(r"([\w\-./\\]+\.py):(\d+):", block_text)
            file_path = file_match.group(1) if file_match else None
            line_no = int(file_match.group(2)) if file_match else None

            exc_match = re.search(r"E\s+([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)", block_text)
            exc_type = exc_match.group(1) if exc_match else None
            exc_msg = exc_match.group(2).strip() if exc_match else None

            seen_tests.add(test_name)
            failures.append(
                FailureDetail(
                    test_name=test_name,
                    file_path=file_path,
                    line_number=line_no,
                    exception_type=exc_type,
                    message=exc_msg,
                )
            )

    # 2. Also check short summary info lines like:
    # FAILED test_calculator.py::test_division_by_zero - ZeroDivisionError: division by zero
    for match in re.finditer(r"FAILED\s+([\w\-./\\]+)::([a-zA-Z0-9_]+)\s*-\s*([A-Za-z0-9_]+):\s*(.*)", stdout):
        file_path, test_name, exc_type, exc_msg = match.groups()
        if test_name not in seen_tests:
            seen_tests.add(test_name)
            failures.append(
                FailureDetail(
                    test_name=test_name,
                    file_path=file_path,
                    line_number=None,
                    exception_type=exc_type,
                    message=exc_msg.strip(),
                )
            )

    return failures


def parse_summary_counts(stdout: str) -> Dict[str, int]:
    """Parse pytest summary counts (e.g. '1 failed, 1 passed in 0.15s')."""
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0}

    match_failed = re.search(r"(\d+)\s+failed", stdout)
    if match_failed:
        summary["failed"] = int(match_failed.group(1))

    match_passed = re.search(r"(\d+)\s+passed", stdout)
    if match_passed:
        summary["passed"] = int(match_passed.group(1))

    match_errors = re.search(r"(\d+)\s+error", stdout)
    if match_errors:
        summary["errors"] = int(match_errors.group(1))

    summary["total"] = summary["passed"] + summary["failed"] + summary["errors"]
    return summary


def run_repository_tests(
    repo_dir: Optional[Path] = None,
    test_target: Optional[str] = None,
    timeout_sec: int = MAX_TEST_TIMEOUT_SEC,
) -> TestRunResult:
    """Execute pytest in the target repository using the virtualenv Python interpreter."""
    target_dir = Path(repo_dir) if repo_dir else SAMPLE_REPO_DIR

    if not target_dir.exists():
        raise FileNotFoundError(f"Repository directory does not exist: {target_dir}")

    cmd = [
        str(PYTHON_EXE),
        "-m",
        "pytest",
        "-v",
        "-rA",
    ]
    if test_target:
        cmd.append(test_target)

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        duration = round(time.time() - start_time, 3)
        combined_output = (proc.stdout + "\n" + proc.stderr).strip()

        # Truncate if excessively long
        if len(combined_output) > MAX_OUTPUT_CHARS:
            combined_output = combined_output[:MAX_OUTPUT_CHARS] + "\n... [Output truncated for display]"

        parsed_failures = [asdict(f) for f in parse_pytest_failures(proc.stdout)]
        counts = parse_summary_counts(proc.stdout)

        return TestRunResult(
            passed=(proc.returncode == 0),
            return_code=proc.returncode,
            output=combined_output,
            stdout=proc.stdout[:MAX_OUTPUT_CHARS],
            stderr=proc.stderr[:MAX_OUTPUT_CHARS],
            duration_sec=duration,
            failures=parsed_failures,
            summary=counts,
            timed_out=False,
        )

    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - start_time, 3)
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return TestRunResult(
            passed=False,
            return_code=124,
            output=f"Pytest execution timed out after {timeout_sec} seconds.",
            stdout=stdout,
            stderr=stderr,
            duration_sec=duration,
            failures=[],
            summary={"total": 0, "passed": 0, "failed": 1, "errors": 0},
            timed_out=True,
        )
