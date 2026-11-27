"""One-shot audio output, with completion tied to the actual PortAudio stream."""

from typing import Any

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from chopper.core.models import Candidate
from chopper.core.sample_render import render_candidate


class PreviewPlayer(QObject):
    started = Signal(int)
    finished = Signal(int)
    failed = Signal(int, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._token: int | None = None
        self._stream: Any = None
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._check_stream)

    def play(self, samples: np.ndarray, sample_rate: int, candidate: Candidate, token: int) -> None:
        if not self._stop_owned():
            self.failed.emit(token, "Could not stop the previous preview.")
            return
        try:
            segment = render_candidate(samples, sample_rate, candidate)
        except Exception as exc:  # noqa: BLE001 - report renderer failures to Qt consumers
            self.failed.emit(token, f"Preview failed: {exc}")
            return

        # Retain ownership even if starting or retrieving the stream fails midway.
        self._token = token
        try:
            sd.play(segment, sample_rate, loop=False, blocking=False)
            self._stream = sd.get_stream()
            if self._stream is None:
                raise RuntimeError("Audio output stream unavailable.")
        except Exception as exc:  # noqa: BLE001 - surface all PortAudio errors to Qt consumers
            self._stop_owned(error=f"Preview failed: {exc}")
            return
        self._timer.start()
        self.started.emit(token)

    @Slot()
    def stop(self) -> None:
        self._stop_owned()

    @Slot()
    def _check_stream(self) -> None:
        if self._token is None:
            return
        try:
            active = self._stream.active
        except Exception as exc:  # noqa: BLE001 - exceptions from a timer slot must remain visible
            self._stop_owned(error=f"Preview monitoring failed: {exc}")
            return
        if not active:
            self._stop_owned()

    def _stop_owned(self, *, error: str | None = None) -> bool:
        self._timer.stop()
        token = self._token
        if token is None:
            return True
        try:
            sd.stop(ignore_errors=False)
        except Exception as exc:  # noqa: BLE001 - keep ownership to retry a failed stop before any new play
            message = f"Could not stop preview: {exc}"
            self.failed.emit(token, f"{error} ; {message}" if error else message)
            return False
        self._token = None
        self._stream = None
        if error is None:
            self.finished.emit(token)
        else:
            self.failed.emit(token, error)
        return True
