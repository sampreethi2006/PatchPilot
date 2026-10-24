# PatchPilot Architecture & Data Flow Specification

## 1. System Overview

**PatchPilot** is structured around a modular Python/Flask backend and a vanilla JavaScript developer dashboard, integrated with a local TypeScript-based **Meterless H-MEM** episodic memory engine and an automated `pytest` execution harness.

```mermaid
graph TD
    User["Developer / Web Dashboard"] -->|HTTP / JSON| Flask["Flask API Server (app.py)"]
    
    subgraph CoreEngine ["PatchPilot Core Engine (core/)"]
        Config["config.py<br/>Environment & Path Resolver"]
        TestRunner["test_runner.py<br/>Isolated Pytest Execution Harness"]
        Diagnostics["diagnostics.py<br/>AST & Traceback Root-Cause Analyzer"]
        Patching["patching.py<br/>Unified Diff & Safe Patch Engine"]
        AIProvider["ai_provider.py<br/>Pluggable Model Interface"]
        HMEMClient["hmem.py<br/>Python Bridge to H-MEM"]
    end
    
    Flask --> Config
    Flask --> TestRunner
    Flask --> Diagnostics
    Flask --> Patching
    Flask --> AIProvider
    Flask --> HMEMClient
    
    subgraph StorageAndExecution ["Execution & Storage"]
        SampleRepo["sample_repo/<br/>Target Python Codebase"]
        HMEM_Bridge["integrations/hmem-cli.ts<br/>TypeScript CLI Bridge via Node.js TSX"]
        MemoryLedger["patchpilot-memory/<br/>Local Ledger & Working Memory State"]
    end
    
    TestRunner -->|Executes Subprocess| SampleRepo
    Patching -->|Validates & Writes| SampleRepo
    HMEMClient -->|Subprocess JSON IPC| HMEM_Bridge
    HMEM_Bridge -->|State Storage| MemoryLedger
```

---

## 2. Component Responsibilities

| Component | Location | Responsibility |
|---|---|---|
| **App Entrypoint** | [app.py](file:///C:/Users/sampr/PatchPilot/app.py) | Exposes REST endpoints (`/api/health`, `/api/diagnose`, `/api/patch/*`, `/api/memory/*`) and serves the UI. |
| **Config Resolver** | [core/config.py](file:///C:/Users/sampr/PatchPilot/core/config.py) | Safely resolves `.venv` Python, Node.js binary, TSX CLI, timeouts, and security policies. |
| **Test Runner** | [core/test_runner.py](file:///C:/Users/sampr/PatchPilot/core/test_runner.py) | Executes `pytest` with timeouts, captures stdout/stderr, and parses structured failure traces. |
| **Root-Cause Analyzer** | [core/diagnostics.py](file:///C:/Users/sampr/PatchPilot/core/diagnostics.py) | Analyzes tracebacks, isolates confirmed facts from hypotheses, and filters safe files. |
| **Patch Engine** | [core/patching.py](file:///C:/Users/sampr/PatchPilot/core/patching.py) | Generates unified diffs, enforces path traversal security, writes backups (`.orig.bak`), and verifies fixes. |
| **AI Provider** | [core/ai_provider.py](file:///C:/Users/sampr/PatchPilot/core/ai_provider.py) | Pluggable interface supporting local deterministic analyzer and optional Nebius Studio LLM. |
| **H-MEM Client** | [core/hmem.py](file:///C:/Users/sampr/PatchPilot/core/hmem.py) | Python subprocess client invoking Node.js TSX bridge for saving and searching memory entries. |
| **Dashboard UI** | [templates/index.html](file:///C:/Users/sampr/PatchPilot/templates/index.html) | Responsive developer dashboard with real-time health indicator, diff viewer, and memory cards. |

---

## 3. End-to-End Workflow Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant UI as Dashboard (index.html)
    participant API as Flask API (app.py)
    participant Test as Test Runner (test_runner.py)
    participant Diag as Diagnostics Engine
    participant HMEM as Local H-MEM Bridge
    participant Repo as sample_repo/

    Dev->>UI: Click "Run Bug Diagnosis"
    UI->>API: POST /api/diagnose
    API->>HMEM: search_findings("Python pytest failure...")
    HMEM-->>API: Return relevant prior knowledge
    API->>Test: run_repository_tests(repo_dir)
    Test->>Repo: python -m pytest -v
    Repo-->>Test: Test failure output (ZeroDivisionError)
    Test-->>API: Return structured failure trace
    API->>Diag: explain_root_cause(test_result)
    Diag-->>API: Confirmed facts, hypotheses, proposed fix
    API->>HMEM: save_finding(failure evidence)
    API-->>UI: Return JSON report (diagnostics, diff preview, memories)
    
    Dev->>UI: Review diff & click "Apply Patch & Verify"
    UI->>API: POST /api/patch/apply
    API->>API: Validate path & reject traversal
    API->>Repo: Create backup & write patched code
    API->>Test: Run verification tests
    Test->>Repo: python -m pytest -v
    Repo-->>Test: All tests pass (return code 0)
    API->>HMEM: save_finding("Patch verified successfully...")
    API-->>UI: Return success & verified status
```

---

## 4. Security Boundaries & Path Traversal Prevention

1. **Path Traversal Rejection**:
   All file paths submitted to `/api/patch/apply` are validated in [`validate_relative_path`](file:///C:/Users/sampr/PatchPilot/core/patching.py#L38-L62):
   - Rejects relative path escapes (`..`, `/`, `\`).
   - Rejects absolute paths (`C:\...`).
   - Resolves target paths and strictly verifies: `target.relative_to(repo_root)`.
2. **Protected File Exclusions**:
   Modifications to `.env`, `.git`, `credentials`, `secrets`, and private keys are rejected.
3. **Subprocess Isolation Limitations**:
   Repository tests are executed inside the Python virtual environment with a hard process timeout (`MAX_TEST_TIMEOUT_SEC = 15s`). Note: On native Windows without containerization (Docker/WSL), Python subprocess isolation does not constitute a kernel-level sandbox. Untrusted foreign code must be reviewed before execution.
4. **Credential Isolation**:
   No credentials or API keys are hardcoded. Cloud provider variables (`NEBIUS_API_KEY`) are read strictly from system environment variables or local uncommitted `.env`.
