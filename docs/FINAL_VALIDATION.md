# Final manual validation — Chopper

Automated checks pass, including the full suite under native Wayland. Hardware
audio, desktop-driver rendering and real DAW imports still need this manual check.
Use a test DAW project and your own source audio; Chopper must never change it.

1. In a Wayland session, launch `uv run chopper` without a platform override.
   Load a track, zoom, scroll and resize the window. Check for stripes, stale
   painting or misaligned sample rectangles. Try a long track and overlapping samples.
2. Check KDE light/dark appearance and **Settings → Force dark mode**. Click and
   click again to preview/stop; verify natural playback completion clears the
   playing indicator. Check stereo playback on the actual output device.
3. Use Ctrl+click and **M** to mark without starting playback; use Space and Esc.
   In Settings, type normally and select text; shortcuts must not affect samples.
4. Export marked samples and all samples from the displayed track. Confirm the
   intended subset, original channels/sample rate and selected WAV/FLAC format.
5. Drag a handle into Bitwig and Dolphin, cancel a drag and retry. If the sample
   folder is unconfigured, choose it, then repeat the first drag. New WAVs stay in
   `dragged/`, including after cancellation; no automatic cleanup is expected.
6. Save the test Bitwig project, close Chopper, reopen the project and verify
   playback. Use **File → Collect and Save** to collect external audio before
   archiving/sharing the project. Do not delete referenced exports.

If native rendering or plugin startup fails, report it. An explicit fallback is:

```bash
QT_QPA_PLATFORM=xcb uv run chopper
```

This is not an automatic fallback. Report whether native Wayland, XCB or both
are affected. Do not treat a returned Qt drop action as proof of a DAW import.
