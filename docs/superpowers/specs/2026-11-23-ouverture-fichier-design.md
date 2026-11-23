# Open an audio file from the command line

Small change, approved in conversation on 23 November 2026: `chopper <file>`
must behave like selecting that track in the library, including analysis and
the usual busy/status indication. Display the waveform when analysis completes.
Without a file, preserve current startup. Missing/unreadable audio must leave
the application usable and show a clear English error.

## Approach

Reuse the existing MainWindow track-selection pipeline, behind a public
`open_file(path: Path) -> None` entry. Schedule it after showing the window,
when the Qt event loop starts. Reimplementing analysis in the CLI would duplicate
behavior; a waveform-only loader would contradict the user's explicit choice.
Let Qt consume its options before parsing the optional single file argument.
Use absolute paths for external callers, including the stems separator.

## Boundaries

Keep Python/PySide6/pyqtgraph and the existing worker/cache pipeline. No Qt in
core, no theme/installation changes, no audio-source writes, no automatic
playback added. Analysis retains its existing cache/model-download side effects.
Each invocation opens a window as today; controlling an existing process is out
of scope. Preserve user changes in the separate habitual checkout.

## Evidence

Pytest: startup without an argument, file startup through real window/worker and
WAV decoding, visible analysis status, waveform/state after completion, missing
file/directory, unreadable file and corrupt audio. Only expensive rhythm inference
may be simulated. Update the permanent external-entry contract in AGENTS.md.
One local implementation commit, then wait for user validation before step 2.
