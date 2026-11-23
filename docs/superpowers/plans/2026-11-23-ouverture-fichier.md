# File startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open and analyze the optional command-line file exactly like library selection.
**Architecture:** Parse Qt's remaining arguments in app.py; defer opening until
the shown window enters its event loop. MainWindow validates the input and calls
the existing track-selection path; workers remain responsible for analysis.
**Tech Stack:** Python 3.12, PySide6, existing pyqtgraph/audio/pytest stack.
**Spec:** docs/superpowers/specs/2026-11-23-ouverture-fichier-design.md

## Global Constraints

- No Qt imports in core. Never modify source audio.
- No theme/installation/dependency changes or real user integration installation.
- Preserve startup without a file and existing analysis progress/error handling.
- Native execution in the already approved isolated checkout, one local commit.
- User explicitly authorized step 1 after confirming automatic analysis; no new
  planning handoff gate. Wait for validation before step 2.

## Review Focus

1. A path with spaces/unicode must remain one argument (startup integration test).
2. Missing path/directory must not start a worker or crash (window tests).
3. Read denial before tags and corrupt decoding inside worker must recover (window tests).
4. No argument must not schedule analysis (startup test).
5. Show the window before starting analysis; preserve busy status and waveform
   output, including Qt options (startup integration and Qt-options tests).

### Task 1: Optional startup file and durable entry contract

**Files:** modify `src/chopper/app.py`, `src/chopper/gui/main_window.py`,
`tests/test_app.py`, `tests/test_main_window.py`, `AGENTS.md`, README and history.
**Interfaces:** `main(argv: list[str] | None = None) -> None`;
`MainWindow.open_file(path: Path) -> None`, using `_on_track_selected` unchanged.

- [x] **1. RED:** tests for optional startup/visible analysis/WAV waveform, no
  argument, missing/directory/permission/corrupt inputs, preserving Qt options.
  Run `uv run pytest -q tests/test_app.py tests/test_main_window.py`; expected
  new failures from missing argument handling/public opening, baseline preserved.
- [x] **2. GREEN:** parse one optional path after QApplication consumes Qt options;
  use `QTimer.singleShot(0, ...)` after show. Public opening validates a regular,
  readable file and reports failure in the status bar; delegates valid input.
- [x] **3. VERIFY:** targeted and full `uv run pytest -q`, Ruff lint/format, mypy,
  Bandit, `git diff --check`. Read-only core-import check; no source-audio changes.
- [x] **4. DOCUMENT/COMMIT:** exact AGENTS external-entry sentence, README usage,
  history with regressions/limits/side effects. Local French commit, hooks intact,
  then stop for user validation; do not install or proceed to theme.

**Evidence:** RED 7 failed/71 passed; GREEN 78 targeted and 807 complete tests.
Static checks pass. One independent focused review found no concrete issue.
No installation/theme/core changes; wait for stage 1 validation after local commit.
