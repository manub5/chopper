# Chopper — first export folder and loop categories

Status: approved by the user on 2026-11-01; no product code changed.

## Intent and agreed direction

The application will be named **Chopper**, with English terminology suited to
home studios. The future GitHub repository is **manub5/chopper**, public.
The existing repository must not be deleted or silently replaced.
Conversation with the user remains in French.

Work proceeds in separate, user-validated steps:
1. Restore the requested loop categories and introduce first-use export setup.
2. Rename the application and translate the interface and user documentation.
3. Audit publication contents and history, then create and publish the public repository.

This short design covers step 1 only. It does not authorize skipping the
remaining interface roadmap steps or publishing unreviewed repository history.

## Current evidence

The user's saved settings enable only `(1.0,)`, with loop settings version 2.
This explains missing fractional loops; the reason that setting was saved is
not yet established. The engine already supports independent per-length quotas.
Export buttons currently prompt without remembering the selected directory;
drag handles are disabled when no directory is configured.

## Approaches

- A fixed Documents folder was proposed, then explicitly rejected by the user.
- Requiring the Settings dialog before dragging is the current behavior and
  does not meet the user's first-use requirement.
- **Chosen:** a brief explanation and folder picker on the first export or
  attempted handle drag; remember the folder and allow later changes in Settings.
  Interrupt and retry the first drag rather than resuming it across a dialog.

## First-use folder contract

- No default export path; no startup prompt or automatic Documents directory.
- An existing configured export directory is preserved and reused.
- With actual samples to export, the first export or threshold-crossing handle
  drag without a configured directory opens a small explanation:

  **Choose your sample folder**

  > Choose where to keep exported samples and audio dragged into your DAW.
  > You can change this folder in Settings at any time.

  Buttons: **Choose folder…** and **Cancel**.
- Choosing a directory records it persistently. A button export then proceeds.
  A first drag writes no audio and starts no native transfer: display
  **Sample folder saved. Drag the sample again to send it to your DAW.**
- The handle must remain available without a configured directory so this
  first-use flow can be reached. A click alone does not open setup.
- Canceling either dialog leaves settings and audio files unchanged.
- A settings write failure is reported, not described as a successful save;
  do not export or start a transfer until setup succeeds. Restore the previous
  in-memory preference on failure.
- Invalid or inaccessible export destinations produce a clear error; never
  silently switch to another folder. Settings remain available to change it.
- Setup must not alter the active sample, marks, or playback.

## Loop categories

- Replace combination presets with three explicit checkboxes: **1 bar**,
  **½ bar**, **¼ bar**, under **Loop lengths**.
- For this explicitly requested correction, re-enable all three lengths once
  through a versioned migration. Preserve subsequent saved choices on reload.
- Require at least one checked length; prevent saving an empty selection with
  an explanatory message rather than silently changing it.
- Preserve the independent quota of up to eight results per enabled loop
  length and eight one-shots, subject to available material. No scoring or
  detector changes, and no guarantee of 32 samples from every track.
- Existing results do not change retroactively; the next analysis uses the
  new settings. Investigate settings round-trips before implementing migration.

## File safety and side effects

- Source audio remains read-only; preserve channels and sample rate.
- Keep durable PCM24 WAVs in the configured folder's existing `glissés/`
  subdirectory for now. Decide the English name during the rename step without
  moving or deleting files already referenced by a DAW project.
- Repeated or canceled native drags deliberately leave distinct WAVs; there
  is no automatic cleanup. Choosing a folder itself generates no audio.
- Bitwig's **Collect and Save** collects external audio into the project.
  Chopper cannot infer the destination project or prove collection from Qt's
  returned drop action.

## Verification required before delivery

Write failing tests before behavior changes, then run the complete test suite.
Cover settings migration and repeated reloads, all three checkbox choices,
empty selection, folder persistence, both cancellation points, failed settings
saves, existing custom paths, first-drag retry, and absence of gesture side
effects. Preserve existing export/collision/partial-error coverage, stereo and
sample-rate checks. Run static and security hooks. Distinguish simulated Qt
transfers from real Wayland/Bitwig user validation.

## Deferred work

The rename step needs its own migration design for Python packaging, launchers,
configuration/cache locations, English user-facing errors and documentation.
Never lose preferences, move referenced WAVs, or rename the user's working
directory implicitly. Historical French documents may remain unchanged.
Before public publication, inspect tracked content and history for secrets,
private paths and audio assets; stop if exposure risks require a decision.
Do not overwrite an existing remote repository or force-push.
