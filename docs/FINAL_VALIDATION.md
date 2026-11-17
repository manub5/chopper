# Final manual validation — Chopper

Manual selection has full-suite automated coverage plus targeted native Wayland
checks at 150% scaling. Hardware
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
7. Left-drag a waveform passage in both directions. Adjust both edges and drag
   inside. Check downbeat snapping, Alt pressed/released during the gesture, and
   free selection on a track without a usable grid. Middle-drag/Shift+wheel pans;
   wheel zooms without moving y. Repeat on the linked sample lanes.
   Cross each handle past the opposite edge, with and without Alt. A tiny motion
   treated as a click must leave the rectangle at the exact original bounds.
8. Choose 2 bars, press C, then repeat with 4 bars. Verify sample rows, rectangles
   and exported lengths. Try a passage shorter than the chosen loop length and
   one with no usable samples. Messages should explain the result without losing
   the selected passage. Use F1 to check C and Esc help.
9. Alternate passage and sample playback. With Auto-preview off, selection stays
   silent but Space still plays the last chosen target. A playback finishing
   during a drag must not reset the rectangle. Chopping/Whole track do not autoplay.
10. Change Length and adjust the passage after a Chop. The warning and Samples from
    bounds should describe the old results. Export them and check those original
    bounds, channels and sample rate, not the adjusted rectangle.
11. Try Whole track, an outside click, Esc, a second Chop, another track, Analyze
    album and closing. Cancel each confirmation first: region, results and marks
    remain, but preview is stopped. Escape/closing the confirmation means Cancel.
    Then test export-and-continue and continue-without-exporting. All manual results
    are exported even when only one is marked. Existing exports must remain intact.
12. Cancel sample-folder setup, or use an unavailable test destination. A failed
    export must not leave manual mode or clear the results. Partial successes
    remain on disk. Never use important existing exports to simulate disk failure.
    Close during a search; if a task cannot finish in time, Chopper must stay open
    with its cache and worker alive, rather than terminate the running thread.

If native rendering or plugin startup fails, report it. An explicit fallback is:

```bash
QT_QPA_PLATFORM=xcb uv run chopper
```

This is not an automatic fallback. Report whether native Wayland, XCB or both
are affected. Do not treat a returned Qt drop action as proof of a DAW import.
