# Manual selection gesture checks

Stage 2 implements the waveform widget only. Passage playback, Chop selection,
Whole track and confirmation dialogs are not connected yet. This checklist is
not a claim of a completed end-to-end feature or a hands-on KDE test.

Stage 3 adds the shared preview state, not the MainWindow/player connection.
Run `uv run pytest -q tests/test_sample_state.py tests/test_preview_player.py`
to check sample/passage token ownership, stale callbacks, explicit playback with
Auto-preview off, and candidate replacement without copying audio or starting
playback. The last selected passage remains the Space target after candidate
replacement; clicking/navigating to a sample selects that sample as the target.
Clearing the passage restores any still-active sample target without playing it.

Stage 4 adds identified background searches using the same in-memory audio and
analysis. Run `uv run pytest -q tests/test_workers.py tests/test_candidate_window.py`
to check manual/automatic lengths, quotas, short/empty selection messages, copied
settings and actual thread completion on both success and failure. These checks
forbid detector, decoder and cache calls during re-ranking. Repeated thread
lifecycle cases also run under Wayland. MainWindow integration and stale-result
rejection remain stage 5 work, not a completed end-to-end check.

## Automated widget checks

Run from the project directory:

```sh
uv run pytest -q tests/test_selection_geometry.py tests/test_waveform_selection.py tests/test_waveform_view.py tests/test_sample_lanes.py
QT_QPA_PLATFORM=wayland QT_SCALE_FACTOR=1.5 uv run pytest -q tests/test_selection_geometry.py tests/test_waveform_selection.py tests/test_waveform_view.py tests/test_sample_lanes.py
```

The tests send physical Qt viewport events with the mouse button held. They cover
creation in either direction, both handles, dragging inside the region, final
Alt modifiers, click versus drag, silent UI updates and cancelled pending signals.
Existing track bounds, linked lane alignment, click/Ctrl-click and y-axis tests
remain active.

## Hands-on checks for the integrated feature

Use a track with known downbeats, then repeat without downbeats:

1. Left-drag on the waveform background in either direction. Both edges snap to
   the nearest downbeat; ties choose the earlier one. No grid means free selection.
2. Drag each edge and the interior. Hold Alt to move freely; release Alt before
   releasing the mouse to snap again. A collapsed snapped range is not expanded
   into an invented bar.
3. Click inside: no new preview request. Click outside: one clear request, with
   the region retained until the future controller approves removal. Drag outside
   to replace the region without issuing a clear request.
4. Middle-drag or Shift+wheel to move horizontally on waveform or sample lanes;
   wheel alone zooms. Right-drag must not scale. Never move beyond the track or
   change the vertical waveform range. Lane left-drag must not pan or edit samples.
5. Resize the window, switch light/dark themes and show a playing sample highlight.
   The manual region remains distinct and the lane time axes stay aligned.
6. Change track or clear the view immediately after a gesture: no delayed finished
   signal from the previous track. Programmatic selection changes are silent.

No gesture writes source audio, exports, preferences or analysis cache. Repeating
a programmatic selection update must not start playback. Repeated physical drags
intentionally produce one finished signal per valid gesture.
