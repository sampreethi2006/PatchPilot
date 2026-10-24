import json
import logging
import os
import sys
from pathlib import Path
from flask import Flask, jsonify, render_template, request

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.ai_provider import get_active_provider
from core.config import (
    BASE_DIR,
    HOST,
    PORT,
    PYTHON_EXE,
    SAMPLE_REPO_DIR,
    VENV_PYTHON,
)
from core.diagnostics import discover_repository_files, explain_root_cause
from core.hmem import is_hmem_ready, run_hmem, save_finding, search_findings
from core.patching import (
    apply_patch,
    propose_patch_for_calculator,
    reset_sample_repository,
)
from core.test_runner import TestRunResult, run_repository_tests

# Setup application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("patchpilot.app")

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Dashboard and Health Endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Serve the PatchPilot AI interactive dashboard."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Return truthful system health status and configuration."""
    hmem_ok, hmem_err = is_hmem_ready()
    _, provider_info = get_active_provider()

    # Verify pytest availability
    pytest_available = False
    try:
        import pytest
        pytest_available = True
    except ImportError:
        pass

    sample_repo_exists = SAMPLE_REPO_DIR.exists()
    calculator_exists = (SAMPLE_REPO_DIR / "calculator.py").exists()
    test_exists = (SAMPLE_REPO_DIR / "test_calculator.py").exists()

    return jsonify({
        "status": "ok",
        "app": "PatchPilot AI",
        "version": "1.0.0",
        "environment": {
            "python_executable": str(PYTHON_EXE),
            "python_version": sys.version.split()[0],
            "virtualenv_detected": VENV_PYTHON.exists(),
            "pytest_available": pytest_available,
            "host": HOST,
            "port": PORT,
        },
        "hmem": {
            "ready": hmem_ok,
            "error": hmem_err,
        },
        "sample_repository": {
            "exists": sample_repo_exists,
            "calculator_exists": calculator_exists,
            "test_exists": test_exists,
            "path": str(SAMPLE_REPO_DIR),
        },
        "ai_provider": provider_info,
    })


@app.route("/api/repo/files", methods=["GET"])
def list_repo_files():
    """List relevant Python source and test files in the sample repository."""
    try:
        files = discover_repository_files(SAMPLE_REPO_DIR)
        return jsonify({
            "status": "success",
            "repository": str(SAMPLE_REPO_DIR),
            "files": files,
            "count": len(files),
        })
    except Exception as exc:
        logger.exception("Failed to discover repository files")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# Diagnosis and Testing Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/diagnose", methods=["POST"])
def diagnose():
    """Execute tests, analyze root cause, query & update H-MEM, and propose a fix."""
    try:
        data = request.get_json(silent=True) or {}
        test_target = data.get("test_target")

        # Step 1: Pre-diagnosis memory retrieval for relevant context
        pre_retrieved_memory = {}
        try:
            pre_retrieved_memory = search_findings("Python pytest ZeroDivisionError divide failure")
        except Exception as exc:
            logger.warning(f"Pre-diagnosis memory search failed: {exc}")

        # Step 2: Execute pytest test suite in controlled runner
        test_result: TestRunResult = run_repository_tests(
            repo_dir=SAMPLE_REPO_DIR,
            test_target=test_target,
        )

        # Step 3: Explain root cause and separate confirmed facts from hypotheses
        root_cause_data = explain_root_cause(test_result, SAMPLE_REPO_DIR)

        # Step 4: Propose minimal patch for review
        patch_proposal = propose_patch_for_calculator(SAMPLE_REPO_DIR)

        diagnosis_summary = (
            "All tests passed in repository."
            if test_result.passed
            else f"Detected failure in {len(test_result.failures)} test(s). Traceback analyzed."
        )

        # Step 5: Save evidence to local H-MEM working memory if failure observed
        memory_saved = None
        memory_error = None
        related_findings = None

        if not test_result.passed:
            finding_text = (
                f"PatchPilot diagnosis: {diagnosis_summary}\n"
                f"Failing tests: {[f.get('test_name') for f in test_result.failures]}\n"
                f"Root cause: {root_cause_data.get('root_cause')}\n"
                f"Test output snippet:\n{test_result.output[:3000]}"
            )

            try:
                memory_saved = save_finding(
                    content=finding_text,
                    source="sample_repo/test_calculator.py",
                    confidence=0.95,
                    tags=["bug:pytest-failure", "language:python", "module:calculator"],
                )
                related_findings = search_findings("division by zero test failure traceback")
            except Exception as exc:
                logger.exception("H-MEM integration encountered an issue")
                memory_error = str(exc)
        else:
            try:
                related_findings = search_findings("Python calculator division")
            except Exception as exc:
                memory_error = str(exc)

        # Merge pre-retrieved findings if current related findings are empty
        if not related_findings or not related_findings.get("memories"):
            if pre_retrieved_memory and pre_retrieved_memory.get("memories"):
                related_findings = pre_retrieved_memory

        return jsonify({
            "status": "success",
            "tests_passed": test_result.passed,
            "return_code": test_result.return_code,
            "duration_sec": test_result.duration_sec,
            "output": test_result.output,
            "summary": test_result.summary,
            "failures": test_result.failures,
            "diagnosis": diagnosis_summary,
            "root_cause": root_cause_data,
            "patch_proposal": patch_proposal,
            "memory_saved": memory_saved,
            "related_findings": related_findings,
            "memory_error": memory_error,
        })

    except Exception as exc:
        logger.exception("Diagnosis workflow failed unexpectedly")
        return jsonify({
            "status": "error",
            "diagnosis": f"Error running diagnosis: {exc}",
        }), 500


# ---------------------------------------------------------------------------
# Patching and Verification Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/patch/propose", methods=["POST"])
def propose_patch_endpoint():
    """Propose a safe, minimal patch with unified diff for review."""
    try:
        proposal = propose_patch_for_calculator(SAMPLE_REPO_DIR)
        return jsonify({
            "status": "success",
            "proposal": proposal,
        })
    except Exception as exc:
        logger.exception("Failed to generate patch proposal")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/patch/apply", methods=["POST"])
def apply_patch_endpoint():
    """Apply approved patch, verify with tests, and record outcome to H-MEM."""
    try:
        data = request.get_json(silent=True) or {}
        file_path = data.get("file_path", "calculator.py")
        patched_code = data.get("patched_code")

        result = apply_patch(
            repo_dir=SAMPLE_REPO_DIR,
            file_rel_path=file_path,
            patched_code=patched_code,
        )

        if not result.get("success"):
            return jsonify({
                "status": "error",
                "message": result.get("error", "Patch application failed validation."),
            }), 400

        # If fix verified by tests, save knowledge into H-MEM
        memory_result = None
        if result.get("verified"):
            try:
                memory_result = save_finding(
                    content=(
                        f"Patch verified successfully for {file_path}. "
                        "Added zero divisor validation raising ValueError. All tests passed."
                    ),
                    source=f"sample_repo/{file_path}",
                    confidence=1.0,
                    tags=["fix:verified", "language:python", "status:resolved"],
                )
            except Exception as exc:
                logger.warning(f"Could not record fix to H-MEM: {exc}")

        return jsonify({
            "status": "success",
            "patch_result": result,
            "memory_saved": memory_result,
        })

    except Exception as exc:
        logger.exception("Failed to apply patch")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/repo/reset", methods=["POST"])
def reset_repo_endpoint():
    """Reset the sample repository to its pristine intentional bug baseline."""
    try:
        reset_result = reset_sample_repository(SAMPLE_REPO_DIR)
        return jsonify({
            "status": "success",
            "result": reset_result,
        })
    except Exception as exc:
        logger.exception("Failed to reset sample repository")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# Memory Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/memory/search", methods=["POST"])
def memory_search_endpoint():
    """Query H-MEM memory directly."""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get("query", "").strip()
        results = search_findings(query)
        return jsonify({
            "status": "success",
            "query": query,
            "results": results,
        })
    except Exception as exc:
        logger.exception("Memory search failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/memory/save", methods=["POST"])
def memory_save_endpoint():
    """Save an observation directly to H-MEM."""
    try:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()
        source = data.get("source", "user")
        confidence = float(data.get("confidence", 0.9))
        tags = data.get("tags", ["source:manual"])

        if not content:
            return jsonify({"status": "error", "message": "Content is required"}), 400

        result = save_finding(content=content, source=source, confidence=confidence, tags=tags)
        return jsonify({
            "status": "success",
            "saved": result,
        })
    except Exception as exc:
        logger.exception("Memory save failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "message": "HTTP Method Not Allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info(f"Starting PatchPilot development server on http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
