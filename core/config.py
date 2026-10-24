import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Python environment resolution:
# Prefer .venv python if present and valid; fallback to sys.executable
VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
if VENV_PYTHON.exists():
    PYTHON_EXE = VENV_PYTHON
else:
    PYTHON_EXE = Path(sys.executable)

# Sample repo directory
SAMPLE_REPO_DIR = BASE_DIR / "sample_repo"

# Node.js resolution: check PATH first, then typical Windows Program Files location
SYSTEM_NODE = shutil.which("node")
if SYSTEM_NODE:
    NODE_EXE = Path(SYSTEM_NODE)
else:
    DEFAULT_NODE = Path(r"C:\Program Files\nodejs\node.exe")
    NODE_EXE = DEFAULT_NODE

# TSX and H-MEM CLI paths
TSX_CLI = (
    BASE_DIR
    / "meterless-hmem"
    / "reference"
    / "node_modules"
    / "tsx"
    / "dist"
    / "cli.mjs"
)
HMEM_CLI = BASE_DIR / "integrations" / "hmem-cli.ts"
HMEM_MEMORY_DIR = BASE_DIR / "patchpilot-memory"

# Server configuration
HOST = os.environ.get("PATCHPILOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("PATCHPILOT_PORT", 5000))

# Subprocess & safety limits
MAX_TEST_TIMEOUT_SEC = 15
MAX_HMEM_TIMEOUT_SEC = 10
MAX_OUTPUT_CHARS = 10000
MAX_SOURCE_FILE_SIZE_BYTES = 500_000
FORBIDDEN_FILE_PATTERNS = {
    ".env",
    ".git",
    "credentials",
    "secrets",
    "id_rsa",
    ".aws",
    ".gcp",
}
