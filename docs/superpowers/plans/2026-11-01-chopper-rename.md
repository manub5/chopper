# Chopper Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Chopper with an English home-studio interface, coherent packaging and non-destructive preference migration.

**Architecture:** Rename the existing Python package without redesigning the engine. Keep settings fallback explicit and read-only; new saves/cache use platformdirs under `chopper`. Translate owned UI copy and route new permanent drags to `dragged/` without touching old exports.

**Tech Stack:** Python 3.12, uv, Hatchling, PySide6, pytest, existing audio stack; no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-01-chopper-rename-design.md`.

## Execution status — 2026-11-02

- [x] Task 1: package, entry points, installer and legacy preference fallback (`d89b5a1`).
- [x] Task 2: English interface and `dragged/` (`f47b7e4`).
- [x] Task 3: current English documentation and instructions (`d7950a9`).
- [x] Independent read-only review; broken-settings-symlink finding reproduced
  with three failing tests, corrected in one RED→GREEN pass.
- [ ] User validation; no remote changes, merge or publication in this step.

The detailed original checklists below serve as task briefs; per-step evidence
and commands are in this plan's execution ledger. The pre-existing Semgrep update
was committed separately (`c95ca2a`) with explicit user authorization.

## Global Constraints

- Conversation remains in French; new code comments and identifiers are English.
- Keep source audio, existing exports, old configuration/cache and the checkout directory untouched.
- No dependency upgrade, detector change, shortcuts roadmap work or automatic WAV cleanup.
- No GitHub creation, remote modification, push, merge or history rewrite in this plan.
- Preserve every pre-commit hook and use French commit messages.
- Execute inline on the existing feature branch; no new worktree required by this approved scope.
- Tests use temporary XDG locations, never real preferences or host installer side effects.
- Preserve sample channels/rate, quotas, playback and independent active/marked states.

## Review Focus

1. Both old and new settings exist: the new settings win even when deliberately restricted (Task 1).
2. Explicit missing paths or malformed new settings must never silently import unrelated old preferences (Task 1).
3. Old launcher compatibility and launcher execution from directories containing spaces must work (Task 1).
4. Existing `glissés/` WAVs referenced by DAWs remain byte-identical after new drags (Task 2).
5. English failure paths and plural sample counts must remain informative, not merely English happy-path buttons (Task 2).

## File Map

- Move all tracked package files from `src/choppeur/` to `src/chopper/`, preserving module layout and `py.typed`; update active imports in `tests/`, `evaluate.py` and `prototypes/drag_drop_wayland.py`.
- Modify `pyproject.toml`, `uv.lock`, `install.sh`, `.gitignore`: metadata, wheel package, main command, temporary old-command alias and generated launcher.
- Modify renamed `core/settings.py`: `APP_NAME`, new default paths, legacy settings fallback only for implicit default loads.
- Modify renamed GUI files and application-owned core error messages: English copy only, no algorithm changes.
- Modify renamed `core/exporting.py`: new drag subdirectory.
- Extend `tests/test_app.py`, `tests/test_settings.py`, existing GUI/export tests; add `tests/test_install.py` and `tests/test_packaging.py`.
- Translate `README.md`; update active commands/layout in `AGENTS.md`, `CLAUDE.md` and current-use instructions in `prototypes/README.md`; append `docs/HISTORIQUE.md`. Leave historical plans/results intact.

## Task 1: Package Identity, Launchers and Safe Preference Fallback

**Interfaces:** Produce `chopper.app:main`, `chopper.core.settings.Settings`, existing `load_settings(path: Path | None = None) -> Settings`, `save_settings(settings: Settings, path: Path | None = None) -> None`, `default_settings_path() -> Path`, `default_cache_path() -> Path`. Keep signatures unchanged. Add private `_legacy_settings_path() -> Path` for platformdirs `choppeur` lookup.

- [ ] **1. Establish baseline:** inspect git status and run `uv run pytest -q`; expected 357 passing tests. Record a plan-specific ledger and base SHA; preserve unrelated work.
- [ ] **2. Write RED identity tests** in `tests/test_packaging.py` using delayed imports and TOML metadata: import `chopper.app` and verify the callable entry point, `project.name == 'chopper'`, primary and legacy console commands both resolve to `chopper.app:main`, wheel package is `src/chopper`. Run `uv run pytest -q tests/test_packaging.py`; expect missing new import/metadata failures.
- [ ] **3. Rename package and active imports**, updating pyproject and lock metadata with the existing uv tooling (consult official docs first). Do not change pinned dependency versions. Keep old command alias, not an old package shim. Run `uv sync --locked` then the full suite after updating the one intentional default-path expectation.
- [ ] **4. Write RED settings tests** with isolated XDG config/cache roots: old-only load returns legacy values, including export path, auto-preview/theme and selected loop lengths; reading creates no new settings file; save writes only new path and leaves legacy bytes intact. Both files exist: new wins. Explicit missing path: defaults, no fallback. Invalid/unreadable new file: exception, no fallback. No legacy file: defaults. Cache path is new and old cache remains intact. Run `uv run pytest -q tests/test_settings.py`; observe intended fallback failures.
- [ ] **5. Implement `load_settings` fallback** only when `path is None` and the new default path is absent. A supplied path is authoritative. Set `APP_NAME = 'chopper'`; retain atomic saves and loop migration version 3 without another reset. No cache copying/deletion and no startup write.
- [ ] **6. Write RED installer tests** in `tests/test_install.py`: copy installer into a temporary spaced-path project; provide stub `uv`, `uname`, `apt-get`, `dpkg` (all packages already installed), and controlled HOME/PATH. Run installer via bash without network/sudo; assert `./chopper` exists and is executable; execute it from another directory with arguments and verify stub uv receives `run chopper` plus those arguments from project cwd. Keep a pre-existing old launcher sentinel byte-identical. Run tests before installer changes.
- [ ] **7. Update `install.sh` and `.gitignore`** for the new generated launcher and brand; keep old ignored launcher and console alias for compatibility. Do not run the installer on the host or delete its old generated launcher. Handle an existing non-generated `./chopper` safely (refuse rather than overwrite); test that refusal with a sentinel file.
- [ ] **8. GREEN gate:** `uv run pytest -q`; `uv sync --locked`; build wheel into approved temporary storage with `uv build --wheel --out-dir <temporary-dir>` and inspect it for `chopper/app.py`, `chopper/py.typed`, and both entry points. Do not publish/install artifacts globally.
- [ ] **9. Commit:** `Renomme le paquet Chopper et préserve les anciens paramètres`, including identity/migration/installer tests; run all existing hooks.

## Task 2: English Home-Studio Interface and Durable Drag Location

**Interfaces:** Keep all GUI signals and method signatures. `sample_type_label(candidate: Candidate) -> str` yields `1-bar loop`, `½-bar loop`, `¼-bar loop`, `One-shot`. `export_drag(..., export_dir: Path) -> Path` writes to `export_dir / 'dragged'`. No candidate/audio schema changes.

- [ ] **1. Write RED GUI tests** for window title `Chopper`; buttons `Open library…`, `Analyze album`, `Settings…`, `Auto-preview`; table headings `Type`, `BPM`, `Length`, `Position`; actions `Export marked (n)` / `Export all (n)`; four sample labels and `Time` waveform axis. Use real widgets and existing state, not source-string searches. Update existing French assertions deliberately; run targeted tests to observe missing English behavior.
- [ ] **2. Add RED Settings dialog tests**: `Settings` title, `Library folder`, `Sample folder`, `Browse…`, `Export format`, `Loop lengths`, `Samples per category`, `Max. one-shot length (s)`, `Processing device`, `Appearance`, `Force dark mode`. Preserve three checkboxes, quota bounds, validation and edited-settings round-trip. Keep stored enum values `auto`/`cpu` stable; display `Automatic`/`CPU only` with item data, so existing saved preferences remain valid.
- [ ] **3. Add RED error/status tests** covering analysis start/failure/completion, disconnected library, empty selection, partial export naming successful files, invalid format, no audio-output stream, failed WAV creation and retained path after canceled/failed platform transfer. Assert owned English prefixes, paths/counts and state safety; preserve raw dependency diagnostics. Keep tests with injected French exception payloads as evidence that raw diagnostics are not translated.
- [ ] **4. Translate GUI and owned core exceptions** in renamed files, including MainWindow QMessageBox titles, SettingsDialog, CandidatesPanel, waveform axis, preview player, presentation, audio loading/export errors, candidates/naming validation and sample drag. Use the specified terminology, retain numerical formats, Qt theme behavior and all interaction semantics. No menus/shortcuts added. Native dialog/OS diagnostic language is outside app-owned copy.
- [ ] **5. Add RED permanent-file test** before changing `core/exporting.py`: create `glissés/old.wav` sentinel, export a new drag, assert new WAV parent is `dragged/`, old file bytes unchanged, repeat yields distinct WAVs and preserves both. Update existing expected parent paths to `dragged/`; do not rename existing test artifacts or sources merely for branding. Run `uv run pytest -q tests/test_exporting.py tests/test_sample_drag.py` to observe path failures.
- [ ] **6. Implement new drag path** in `core/exporting.py`; preserve PCM24, original channels/rate, atomic collision handling and no cleanup. First-use setup/retry dialog remains unchanged and English.
- [ ] **7. GREEN full gate:** `uv run pytest -q`; run targeted GUI/export tests under `QT_QPA_PLATFORM=wayland` when available, still simulating modal interaction and QDrag.exec. Report this limitation explicitly. Re-check desktop theme and long English-label sizing without changing the approved layout.
- [ ] **8. Commit:** `Traduit l’interface pour les home-studios et range les nouveaux glissers`.

## Task 3: User Documentation, Active Instructions and Final Verification

**Interfaces:** Document actual Task1/2 launch commands and migration behavior, not a published repository that does not yet exist.

- [ ] **1. Translate README**: Chopper overview, Linux requirements, installer/manual launch commands, first-use sample-folder setup, four categories and quotas, Preview/mark/export behavior, permanent drag files and Bitwig `Collect and Save`, KDE/Wayland override if needed. Explain optional GPU, first-run download, migration and possible initial cache reanalysis. Do not claim new shortcuts or a working public GitHub URL.
- [ ] **2. Update active developer commands/layout** in AGENTS.md and CLAUDE.md to `chopper`/`src/chopper/`/new XDG paths without removing permanent safety rules or hooks; these instructions may remain French. Update prototype active import/run instructions and name where currently shown, leaving the probe explicitly disposable and historical results untouched. Append HISTORIQUE with old/new settings precedence, new cache, old launcher alias and immovable old WAVs.
- [ ] **3. Verify:** full pytest; Ruff lint and format check over `src tests prototypes evaluate.py`; mypy on those paths; Bandit using existing configuration; `git diff --check`; locked sync and wheel inspection. Review remaining `choppeur`/French mentions manually, allowing only legacy compatibility, history/comments and raw user data. No blanket text replacement in historical files or fixtures.
- [ ] **4. Commit:** `Documente Chopper en anglais et sa migration non destructive`.
- [ ] **5. Independent read-only review** of the complete rename range against this plan/spec, especially five Review Focus cases. Fix demonstrated Critical/Important findings in one TDD pass with full regression verification; ledger minor deferrals and any scope rulings. No merge or publication.
- [ ] **6. Deliver for user validation** with exact test counts, commit IDs, `uv run chopper` launch command, migration/cache side effects and simulated-vs-real Wayland test limits. Wait for validation before the public-repository audit/publication step.

## Self-Review

Package/migration/launcher behavior belongs to Task1; visible copy and new WAV
location to Task2; current documentation and whole-change review to Task3.
Review Focus cases have explicit tests. Default settings fallback never applies
to explicit test paths. Cache recreation and the temporary legacy command alias
are implementation choices documented openly; neither deletes legacy data.
Dependency pins, metadata schemas and audio algorithms remain unchanged.
