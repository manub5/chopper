"""One-shot audio output, with completion tied to the actual PortAudio stream."""

import math
from typing import Any

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from chopper.core.models import Candidate


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
        if (
            not math.isfinite(sample_rate)
            or sample_rate <= 0
            or samples.ndim not in (1, 2)
            or (samples.ndim == 2 and samples.shape[1] == 0)
            or not math.isfinite(candidate.start_seconds)
            or not math.isfinite(candidate.end_seconds)
            or candidate.end_seconds <= candidate.start_seconds
        ):
            self.failed.emit(token, "Invalid audio or preview boundaries.")
            return
        # Clamp in seconds first: negative slicing and huge products are unsafe.
        duration = len(samples) / sample_rate
        start = round(min(duration, max(0.0, candidate.start_seconds)) * sample_rate)
        end = round(min(duration, max(0.0, candidate.end_seconds)) * sample_rate)
        segment = samples[start:end]
        if len(segment) == 0:
            self.failed.emit(token, "This sample is empty (zero length).")
            return
        if not np.isfinite(segment).all():
            self.failed.emit(token, "This sample contains non-finite audio values.")
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
