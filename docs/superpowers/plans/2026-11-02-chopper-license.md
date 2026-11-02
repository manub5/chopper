# Chopper License Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the user-approved Chopper Source-Available License 1.0, credited to M.B, without changing its terms.

**Architecture:** Root LICENSE is authoritative. README summarizes its distinction between commercial audio use and software commercialization; package metadata and built artifacts carry the same license. No runtime code changes.

**Tech Stack:** Existing Python 3.12, uv, Hatchling, pytest; no added dependency.

**Spec:** `docs/superpowers/specs/2026-11-02-chopper-license-draft.md`, approved on 2026-11-02.

## Execution status

- [x] Apply approved text and package metadata; README/history updated.
- [x] Real wheel and sdist: full license bundled, custom metadata verified,
  approved text byte-identical (3077 bytes).
- [x] Full regression suite: 382 passed; Ruff, mypy and diff checks passed.
- [ ] Commit, independent read-only review and final historical secret scan.
- [ ] User validation before separate publication checkpoint.

## Global Constraints

- Copy the approved license body verbatim, including `Copyright (c) 2026 M.B`.
- Allow commercial samples, sample packs, music and paid production, including business use.
- Do not expand the approved software-sale restriction to unrelated activities.
- Preserve third-party licenses and required source-audio rights.
- Describe the license as custom source-available, not MIT, generic noncommercial or OSI-approved open source.
- No source audio changes, runtime changes, dependency upgrades, history rewrite or remote changes.
- No GitHub creation or push in this step; publication follows separately.
- Work inline on the existing branch, preserve all hooks, then report tests and wait for validation.

## Review Focus

1. Built wheel must include the full license, not only its metadata label.
2. Source distribution must also contain LICENSE.
3. Metadata must not falsely identify a standard SPDX license.
4. README summary must not accidentally prohibit paid audio work or require royalties on outputs.
5. Third-party and source-audio rights must remain explicitly outside the grant.

## Task 1: Apply and Package the Approved License

**Files:** Create `LICENSE`; modify `README.md`, `pyproject.toml`, `docs/HISTORIQUE.md` and the status introduction in the approved licensing document. No application or test-module changes unless artifact verification demonstrates a packaging issue.

**Interfaces:** PEP 639 project metadata `license = "LicenseRef-Chopper-Source-Available-1.0"`, `license-files = ["LICENSE"]`; installed metadata must expose `License-Expression` and `License-File`, with license bytes included in distributions.

- [ ] **1. Baseline and evidence:** inspect git status and record base SHA. Read the approved body starting at `# Chopper Source-Available License 1.0`. Check current official packaging/Hatch documentation for custom LicenseRef and license-files support before editing metadata.
- [ ] **2. Artifact RED check:** build current wheel and sdist to plan-specific approved temporary storage using `uv build --out-dir <directory>`. Inspect ZIP/tar contents and wheel METADATA; confirm full LICENSE/custom expression are absent. This is packaging verification, not a prose unit test; do not create tests that merely compare documentation strings.
- [ ] **3. Apply text:** create root `LICENSE` with the complete approved body, unchanged. Update pyproject license expression and license-files. Do not add a different standard license, author identity, legal clause or copyright claim for dependencies.
- [ ] **4. Document accurately:** README License section links LICENSE and explains permitted commercial audio, free redistribution/modification conditions, and prior written authorization for selling/licensing/including the software or derivatives in paid software products. Note source-available status and source-audio/third-party exclusions. Append HISTORIQUE; mark the approved document applied, retaining the approved body unchanged.
- [ ] **5. Artifact GREEN check:** rebuild wheel and sdist into a separate temporary output folder. Inspect wheel `METADATA`: exact custom `License-Expression`, `License-File: LICENSE`; inspect the bundled `*.dist-info/licenses/LICENSE` and sdist root LICENSE, requiring byte equality with the repository LICENSE. Verify body equality against the approved document and check no MIT/noncommercial mislabel was introduced.
- [ ] **6. Regression and security:** `uv run pytest -q` (baseline 382); `uv run ruff check src tests prototypes evaluate.py`; `uv run mypy src tests prototypes evaluate.py`; `git diff --check`; refresh `gitleaks git . --log-opts="--all" --redact --no-banner` after committing, and inspect added content for private paths. Artifact checks cover Review Focus1–3; read README and full grant together to cover4–5. No automated test proves legal enforceability.
- [ ] **7. Commit:** `Applique la licence Chopper validée par M.B`, with all hooks enabled. Report commit, exact tests, artifact inclusion, and legal-review caveat. No external publication before the separate publication checkpoint.

## Self-Review

All changes concern licensing distribution, not audio functionality. The approved
body remains the single source for legal terms; custom metadata is explicitly a
LicenseRef, not a claim of SPDX/OSI approval. Both artifact formats and README
scope have concrete verification steps. GitHub remains out of this task.
