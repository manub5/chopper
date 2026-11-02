# Chopper — rename and English user experience

Status: direction approved on 2026-11-01; implementation plan approved on 2026-11-02.

## Intent

Rename Choppeur to **Chopper**, including the Python package and launch command,
and present a coherent English application for home-studio users. Keep existing
preferences and referenced audio safe. Conversation remains in French.

## Approaches and approved choice

A title-only rename leaves installation, imports and documentation inconsistent.
The user approved a complete rename, English user-facing copy, non-destructive
preference migration, unchanged old WAV locations, and `dragged/` for new drags.
Do not rewrite historical documents merely to replace old names.

## Contract

- Project/distribution/package/primary command: `chopper`; window title: `Chopper`.
- Rename `src/choppeur/` to `src/chopper/` and update active imports and tools.
- Translate application-owned labels, buttons, tooltips, status messages,
  dialogs and error prefixes into English. Use **1-bar loop**, **½-bar loop**,
  **¼-bar loop**, **One-shot**, **Preview**, **Auto-preview**, **Export marked**,
  **Export all**, **Settings**, **Sample folder**. Preserve BPM and `mm:ss.mmm`.
- Do not translate track metadata, user paths, or raw third-party/OS diagnostics.
  Native file-picker language may follow the user's desktop locale.
- Translate README and current user-facing installation/use instructions;
  developer/history/design documents may remain French. Update active commands
  and architecture references in project instructions without removing rules.
- Linux/Python 3.12/uv/Qt architecture and every existing hook stay unchanged.
- Keep the current checkout directory, existing remote and source audio untouched.

## Migration details (implementation choices)

- Resolve new configuration/cache paths with platformdirs using `chopper`.
- If the new default settings file is absent, read the old default
  `choppeur/settings.toml` without modifying it. Prefer an existing new file.
  Explicit caller-supplied paths never fall back to user files.
- Write future saves atomically only to the new default path; do not write at
  startup just to migrate. Preserve the export directory and v3 loop selections.
- Do not silently discard an unreadable/malformed new configuration by using
  the old one. Existing load errors remain visible rather than hiding bad data.
- Start a fresh disposable analysis cache under `chopper`; leave the old SQLite
  cache intact. Trade-off: old analyses may need to run again. No risky live
  SQLite copying or deletion is needed for a rename.
- Retain `choppeur` as a temporary console-command alias to the new entry point
  so previously generated launchers still work. The documented command is `chopper`.
  No public compatibility promise for old Python imports is required.
- The installer generates `./chopper`; leave an existing old launcher alone.
- New drags create durable PCM24 WAVs under `<sample folder>/dragged/`.
  Never move, rename or delete existing `glissés/` or other exports. Repeated
  drags remain deliberately non-idempotent; no automatic cleanup.
- The first-use folder dialog and retry-first-drag behavior remain unchanged.

## Non-goals and safety

No audio detector changes, sample-score changes, dependency upgrades, shortcut
roadmap work, repository rename, history rewrite, GitHub creation or push here.
Public `manub5/chopper` publication follows a separate content/history audit.
No new real home-directory folders or user settings are created by development
tests; use isolated XDG directories. Do not run the installer against the host.

## Verification

Test new imports, entry points, distribution build, generated launcher execution
with stubbed external commands, configuration precedence/migration/error paths,
English visible interactions and errors, and new drag location while old WAVs
stay byte-identical. Run the full suite and existing static/security checks.
Explicitly distinguish offscreen/simulated transfer tests from user validation
under Wayland/Bitwig. Finish with an independent read-only review and await
validation before publication.
