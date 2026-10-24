# PatchPilot AI: 3–5 Minute Live Hackathon Demo Script

## Overview
**PatchPilot** is an autonomous software repair and evidence memory agent for Python repositories. It detects bugs through test execution, performs deterministic root-cause analysis, proposes safe reviewable patches, verifies fixes through automated test re-runs, and remembers debugging findings in local **Meterless H-MEM** memory.

---

## Pre-Demo Checklist (30 seconds before presentation)
1. In PowerShell, ensure the application is started:
   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```
2. Open your browser to:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)
3. Confirm the status pill in the top-right shows: **Online: Python 3.11 (Port 5000)** and **H-MEM Active**.

---

## Live Demo Flow

### 1. The Hook (0:00 – 0:45)
> *"Hello judges! Software bugs take hours to diagnose, verify, and document. Meet **PatchPilot**—an autonomous AI coding agent designed to investigate failing repositories, explain root causes with strict evidence, propose reviewable patches, verify them with tests, and preserve debugging knowledge in a local episodic memory system."*

*Point to the dashboard overview:*
- Show the **Repository Target**: `sample_repo/ (Python Calculator)`.
- Show the 6-step workflow tracker: **Inspect → Test & Diagnose → Propose Patch → Review Diff → Apply & Verify → Remember**.

---

### 2. Autonomous Diagnosis & Failure Evidence (0:45 – 1:30)
> *"Let's investigate our repository with one click."*

*Click **⚡ Run Bug Diagnosis**:*
- Observe the real-time execution of the test suite.
- Point to the **Test Execution Evidence** panel:
  - Metric changes to **FAILED**, 1 test failed in `0.08s`.
  - Raw Pytest traceback highlights: `ZeroDivisionError: division by zero` in `calculator.py:3`.
- Point to the **Root-Cause Analysis** panel:
  - **Confirmed Facts**: Show that the system isolates factual observations (`ZeroDivisionError at line 3`, calling code `divide(10, 0)`) from hypotheses.
  - **Hypotheses & Suggested Fix**: Advises adding zero-divisor validation raising `ValueError`.

---

### 3. Safe Patch Review: Human-in-the-Loop Security (1:30 – 2:30)
> *"Autonomous agents should never blindly modify production code. PatchPilot generates a standard, reviewable unified diff and enforces human approval."*

*Scroll to **Proposed Patch Review**:*
- Point out the colorized **Unified Diff**:
  - Green additions (`+ if b == 0: raise ValueError(...)`).
  - Strict path traversal prevention: PatchPilot verifies that targets are inside the repo and creates `.orig.bak` backups.
- Show the human review checkpoint: the agent requires explicit user confirmation before applying.

---

### 4. Apply & Automated Post-Patch Verification (2:30 – 3:30)
> *"Let's approve and apply the patch."*

*Click **🛡️ Apply Patch & Verify Fix** and accept the confirmation dialog:*
- Watch PatchPilot apply the patch and automatically trigger a post-patch verification test run.
- Point to the results:
  - Metric flips to **PASSED** (green).
  - Status badge: **Applied & Verified ✓**.
  - All test assertions succeed with return code `0`.

---

### 5. Preserving Knowledge with Meterless H-MEM (3:30 – 4:15)
> *"What happens to the debugging knowledge? PatchPilot writes findings into a local, meterless H-MEM memory ledger without requiring external cloud databases."*

*Point to the **Local H-MEM Memory** panel:*
- Show the newly recorded memory card with Memory ID, confidence, and source provenance (`sample_repo/calculator.py`).
- Type `division` into the memory search bar and click **Search**.
- Observe instantaneous semantic and lexical retrieval of previous failure and fix findings with relevance percentages.

---

### 6. Repeatability & Wrap-Up (4:15 – 5:00)
> *"For testing and repeatable demonstrations, PatchPilot provides a single-click reset."*

*Click **↺ Reset Baseline Bug**:*
- The sample repository is restored to the intentional division-by-zero bug, baseline tests re-fail, and the demo cycle can be repeated instantly.
- *"PatchPilot turns hours of manual debugging into seconds of verifiable, safe autonomous repair. Thank you!"*
