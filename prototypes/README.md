# Disposable probe: native Wayland drag-and-drop to Bitwig

This Chopper development probe is separate from the application. It does not
modify source tracks, preferences or the analysis cache, and is not a UI mockup.

From the project root in a KDE Wayland session:

```bash
QT_QPA_PLATFORM=wayland uv run python prototypes/drag_drop_wayland.py
```

The first log line must include `Actual Qt backend: wayland`. Unlike the main
application, this probe does not default to XWayland. Report launch failures
rather than silently switching backends.

## Required manual test

1. Open a **test project** in Bitwig with an audio track.
2. Hold the left mouse button on `⠿ Drag this sample` and drop it onto the track.
3. Check that a clip appears and plays four low pulses in a two-second stereo loop.
4. Drag again to a folder in Dolphin; check that the WAV exists and plays.
5. Cancel a drag with Escape and retry; the window must remain usable.
6. Close the probe and check that the imported Bitwig clip still plays.

The log shows the WAV path, local URL and Qt result. `CopyAction` **does not
prove** that Bitwig imported the audio. A sandboxed Bitwig installation, such as
Flatpak, may have different file access from Dolphin; a real test is required.

## Side effects

Each actual drag creates a new `chopper-dnd-probe-*` directory in the system
temporary directory, with a stereo PCM24 WAV at 44,100 Hz (about 530 kB). Clicking
alone creates nothing. Files remain after cancellation or closing the probe,
because Bitwig may still reference them. There is no automatic cleanup here.
These paths are **not suitable for a permanent project**: the system may remove
temporary files, especially after a restart. The main application instead uses
the user's permanent sample folder.

To use another output root, choose an existing directory:

```bash
QT_QPA_PLATFORM=wayland uv run python prototypes/drag_drop_wayland.py --output-root EXISTING_DIRECTORY
```

Automated tests cover real WAVs and local URLs, distinct names, no export on
click and visible write failures. They do not prove a real drop into Bitwig or
Dolphin under Wayland.
