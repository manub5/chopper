# Chopper First Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore all requested loop lengths and remember a user-chosen sample folder on first export or attempted drag.

**Architecture:** Keep audio generation and loop scoring unchanged. Settings own a versioned migration; SettingsDialog projects explicit checkboxes. MainWindow coordinates a small folder-selection helper and persists the selected path before any audio write or native drag.

**Tech Stack:** Python 3.12, PySide6, pytest, uv, existing TOML settings and audio writers; no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-01-chopper-first-export-design.md` (approved).

## Execution status

- [x] Task 1: migration v3 and explicit checkboxes (`b6385ec`); 338 full tests passed.
- [x] Task 2: first-use setup and safe persistence implemented; 357 full tests passed,
  24 targeted tests under Wayland passed with modal/native interactions simulated.
- [ ] Final independent review and any RED→GREEN fixes.
- [ ] User validation under Wayland/Bitwig, then a separate rename step.

Detailed step checklists below are the original execution brief; RED/GREEN evidence
and command results are recorded in this plan's execution ledger and final history entry.

## Global Constraints

- No default export path; no startup prompt or automatic Documents directory.
- An existing configured export directory is preserved and reused.
- Source audio remains read-only; preserve channels and sample rate.
- Keep durable PCM24 WAVs in the configured folder's existing `glissés/` subdirectory for now.
- Canceling either dialog leaves settings and audio files unchanged.
- Setup must not alter the active sample, marks, or playback.
- Conversation with the user remains in French; new product copy is English.
- Do not rename the package, configuration/cache directories, working directory or remote in this plan.
- No GitHub creation/publication, detector changes, automatic audio cleanup or roadmap step 7.
- Execute inline using the existing feature branch; do not discard existing work.
- Stop after the full corrective step, report verification and await user validation.

## Review Focus

1. Failure during settings persistence must not destroy the old TOML or leave a misleading in-memory path (Task 2).
2. Canceling the native folder picker after accepting the explanation must be as harmless as canceling the explanation (Task 2).
3. A stale sample identity or no marked samples must not initiate setup or write unrelated audio (Task 2).
4. A second handle gesture after setup must export exactly once without opening setup again (Task 2).
5. Reopening Settings and changing an unrelated preference must preserve a deliberately restricted loop selection (Task 1).

## File Map

- Modify `src/choppeur/core/settings.py`: loop migration v3 and safe settings persistence.
- Modify `src/choppeur/gui/settings_dialog.py`: three loop checkboxes and empty-selection validation.
- Create `src/choppeur/gui/export_folder_dialog.py`: explanation and folder picker only; no persistence or audio.
- Modify `src/choppeur/gui/main_window.py`: common first-use setup and correct export/drag continuation.
- Modify `src/choppeur/gui/candidates_panel.py`: make setup reachable from the handle without a configured destination.
- Modify `tests/test_settings.py`, `tests/test_settings_dialog.py`, `tests/test_main_window.py`, `tests/test_sample_drag.py`; create `tests/test_export_folder_dialog.py`.
- Update `docs/SPEC.md`, `docs/REFONTE_INTERFACE.md`, `docs/HISTORIQUE.md` and the existing refonte progress ledger to record the superseded destination/disabled-handle contract.

## Task 1: Explicit Loop Lengths and One-Time Restoration

**Interfaces:** Consume `Settings.from_dict(data: dict) -> Settings`, `SettingsDialog.settings() -> Settings`, and `LOOP_LENGTHS_BARS == (0.25, 0.5, 1.0)`. Produce `loop_lengths_version = 3`, `SettingsDialog._loop_length_checks: dict[float, QCheckBox]`, and `SettingsDialog.accept() -> None` validating a nonempty selection.

- [ ] **1. Write migration tests** in `tests/test_settings.py`: `test_v2_lengths_restore_all_once` parameterizes all seven nonempty subsets and absent/malformed versions, asserts all three lengths and version 3 after migration, with unrelated preferences unchanged. Then save a deliberate subset at version 3 and assert two reloads preserve it. Update old v2 normalization tests to use version 3 when testing current-version behavior. Retain read-only loading assertions and test migration version 3 is not downgraded on round-trip.
- [ ] **2. Run RED:** `uv run pytest -q tests/test_settings.py`; confirm missing v3 behavior fails for the intended reason.
- [ ] **3. Implement migration** in `core/settings.py`: defaults use version 3; legacy versions below 3 or invalid versions restore `LOOP_LENGTHS_BARS` once in memory. Loading remains read-only; persistence uses the normal save path. Do not alter quotas or scoring.
- [ ] **4. Write dialog tests** in `tests/test_settings_dialog.py`: parameterize all seven selections; assert labels `1 bar`, `½ bar`, `¼ bar`, exact check states and sorted settings tuple; reopen and edit an unrelated control without changing the tuple. `test_empty_loop_selection_cannot_accept` unchecks all, calls `accept()`, asserts the dialog is not Accepted and an explanatory warning was displayed. Adapt old private combo-control tests rather than retaining an obsolete widget.
- [ ] **5. Run RED:** `uv run pytest -q tests/test_settings_dialog.py`; confirm checkbox/validation assertions fail before implementation.
- [ ] **6. Implement checkboxes** in `gui/settings_dialog.py`, grouped under `Loop lengths`. `settings()` builds the canonical tuple; `accept()` rejects the empty state with `Select at least one loop length.` and otherwise delegates to QDialog. Keep other fields and preferences unchanged. Add no automatic analysis restart.
- [ ] **7. Verify GREEN:** `uv run pytest -q tests/test_settings.py tests/test_settings_dialog.py tests/test_candidates.py`. Investigate unexpected failures before changing expectations. Record that this restores a known saved restriction, not a proven detector failure.
- [ ] **8. Commit** only these production/tests and the approved design/plan: `Rétablit les longueurs de boucle avec des choix explicites` (all existing hooks enabled).

## Task 2: Remember the First Chosen Sample Folder

**Interfaces:** Create `choose_export_folder(parent: QWidget) -> Path | None` in `gui/export_folder_dialog.py`. Add `MainWindow._ensure_export_directory() -> Path | None`, consuming `self.settings.export_dir` and `save_settings(settings: Settings, path: Path | None = None) -> None`. Preserve existing `export_batch`, `export_drag` and `start_file_drag` signatures.

- [ ] **1. Write persistence safety tests** in `tests/test_settings.py`: parameterize serialization and final-replace failures; existing settings bytes remain identical and the exception propagates; no temporary artifact remains. Retain successful round-trips and parent-directory creation tests.
- [ ] **2. Run RED:** `uv run pytest -q tests/test_settings.py`; establish that the current direct write does not preserve an existing TOML on failure.
- [ ] **3. Make `save_settings` safely replace**: serialize before touching the destination, write a uniquely named temporary file in its parent, close it, then atomically replace the TOML; remove only this temporary file on failure. Use standard-library portable paths, no broad cleanup. Do not modify reads, source audio or cache persistence.
- [ ] **4. Write folder dialog tests** in `tests/test_export_folder_dialog.py`: explanation Cancel never opens the picker; picker cancel returns None; success returns the chosen Path. Assert exact approved English title/body/buttons, using real Qt message objects and simulating only modal interaction/picker return. Do not run a native modal picker unattended.
- [ ] **5. Run RED:** `uv run pytest -q tests/test_export_folder_dialog.py`; expect the missing module/contract.
- [ ] **6. Implement `choose_export_folder`** with a small QMessageBox, `Choose folder…` action and default Cancel. Use the spec's exact text; then QFileDialog.getExistingDirectory titled `Choose your sample folder`. Return None for either cancellation. No filesystem creation or settings mutation here. Verify Qt APIs in current official documentation before implementation.
- [ ] **7. Write integration tests** in `tests/test_main_window.py`: existing destination bypasses setup; no startup setup; first button export persists before export; both cancellations do nothing; failed save keeps the old in-memory path, reports the error, writes no WAV and starts no QDrag. Use the real settings writer with an explicit temporary settings path for persistence/reload checks, never user settings.
- [ ] **8. Write gesture tests** in `tests/test_sample_drag.py` and `tests/test_main_window.py`: an unconfigured handle stays usable; click or subthreshold motion does not prompt; threshold-crossing left drag chooses and saves the directory but produces no WAV/QDrag. A new gesture creates exactly one WAV and one native transfer without another prompt. Snapshot active/marked/playing identities to prove setup does not change them. Continue simulating only QDrag.exec for native transfer.
- [ ] **9. Add boundary integration cases**: stale sample ID and empty export selection do not prompt; Unicode/spaced destination persists and is reused; configured destination pointing to a file/unavailable folder reports an error without fallback or new picker. Preserve existing partial exports, collisions, canceled native transfers, and stereo/sample-rate assertions. Replace old assertions requiring disabled unconfigured handles with the new setup contract.
- [ ] **10. Run RED:** `uv run pytest -q tests/test_export_folder_dialog.py tests/test_main_window.py tests/test_sample_drag.py`; confirm intended integration failures.
- [ ] **11. Implement `_ensure_export_directory`**: return existing configured Path; otherwise call chooser, save a `dataclasses.replace` copy with its chosen path, and update `self.settings` only after success. On cancel return None; on failure display `Could not save the sample folder: …` and return None without audio writes. Keep other settings and state untouched.
- [ ] **12. Integrate buttons/handle**: button export calls the helper only after validating candidates and continues after successful setup. Drag records whether setup was needed, calls the helper after validating sample identity, and on first success displays `Sample folder saved. Drag the sample again to send it to your DAW.` then returns before export/QDrag. Existing configured drag behavior stays unchanged. Remove MainWindow's destination-based handle disabling at startup/settings updates; update tooltips to explain first-use setup. Reset handle press before emitting; do not resume the original gesture.
- [ ] **13. Verify GREEN:** `uv run pytest -q tests/test_settings.py tests/test_export_folder_dialog.py tests/test_main_window.py tests/test_sample_drag.py tests/test_exporting.py`. Inspect failures without weakening audio-safety checks.
- [ ] **14. Update specifications/history/ledger** with actual behavior and migration effects. Retain older entries as history; new contract supersedes prior destination and handle rules. Do not claim the full English rename or public repository exists.
- [ ] **15. Full gate:** `uv run pytest -q`; `uv run ruff check src tests prototypes evaluate.py`; `uv run ruff format --check src tests prototypes evaluate.py`; `uv run mypy src tests prototypes evaluate.py`; `uv run bandit -qc pyproject.toml -r src prototypes evaluate.py -ll`; `git diff --check`. Require zero failures; report existing warnings accurately. Check no private paths/secrets entered tracked changes.
- [ ] **16. Commit:** `Mémorise le dossier choisi au premier export ou glisser`, preserving every pre-commit hook. Verify clean status and record exact test count/commit IDs.
- [ ] **17. Hand off for user validation:** first export, cancel both dialogs, restart persistence, first drag followed by retry under Wayland and Bitwig. Report automated regressions and edge coverage, migration behavior (one-time restoration, then stable settings), and intentionally non-idempotent repeated WAV creation. Stop before rename/publication or roadmap step 7.

## Plan Self-Review

The two tasks cover the approved corrective scope without mixing in the rename.
All five review-focus conditions have explicit tests. Interfaces use existing
Settings/export contracts; checkbox order canonicalizes to LOOP_LENGTHS_BARS.
Safe TOML replacement is included because restoring memory alone cannot meet
the promised failed-save behavior. No change to the sample generator, waveform,
theme, source audio, existing exported paths or GitHub remotes is planned.
