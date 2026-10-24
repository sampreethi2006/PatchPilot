import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from core.config import (
    BASE_DIR,
    HMEM_CLI,
    HMEM_MEMORY_DIR,
    MAX_HMEM_TIMEOUT_SEC,
    NODE_EXE,
    TSX_CLI,
)

logger = logging.getLogger("patchpilot.hmem")


def is_hmem_ready() -> Tuple[bool, Optional[str]]:
    """Check if all required binaries and scripts for H-MEM exist."""
    if not NODE_EXE.exists():
        return False, f"Node.js executable not found at: {NODE_EXE}"
    if not TSX_CLI.exists():
        return False, f"TSX CLI runner not found at: {TSX_CLI}"
    if not HMEM_CLI.exists():
        return False, f"H-MEM bridge CLI script not found at: {HMEM_CLI}"
    return True, None


def run_hmem(action: str, *args: str) -> Dict[str, Any]:
    """Execute the local Meterless H-MEM TypeScript bridge.

    Returns parsed JSON dictionary output or raises RuntimeError.
    """
    ready, error_msg = is_hmem_ready()
    if not ready:
        raise FileNotFoundError(error_msg)

    env = os.environ.copy()
    if NODE_EXE.parent.exists():
        env["PATH"] = str(NODE_EXE.parent) + os.pathsep + env.get("PATH", "")

    cmd = [
        str(NODE_EXE),
        str(TSX_CLI),
        str(HMEM_CLI),
        action,
        *args,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=MAX_HMEM_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"H-MEM operation '{action}' timed out after {MAX_HMEM_TIMEOUT_SEC}s") from exc
    except Exception as exc:
        raise RuntimeError(f"H-MEM process execution failed: {exc}") from exc

    if result.returncode != 0:
        err_text = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        raise RuntimeError(f"H-MEM '{action}' failed (exit {result.returncode}): {err_text}")

    # Extract JSON line from output
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    raise RuntimeError(f"H-MEM did not output valid JSON. Stdout: {result.stdout[:300]}")


def save_finding(
    content: str,
    source: str,
    confidence: float = 0.9,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Save a bug diagnosis or fix finding into H-MEM working memory."""
    finding = {
        "content": content,
        "source": source,
        "confidence": confidence,
        "tags": tags or ["project:patchpilot"],
    }
    return run_hmem("save", json.dumps(finding))


def search_findings(query: str) -> Dict[str, Any]:
    """Retrieve related findings from H-MEM based on query terms."""
    clean_query = query.strip()
    if not clean_query:
        return {"ok": True, "context": "", "memories": []}
    return run_hmem("search", clean_query)
