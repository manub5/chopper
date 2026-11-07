"""Disposable native Qt drag-and-drop probe, separate from Chopper's interface."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from chopper.core.audio_io import export_segment


def create_drag_payload(output_root: Path | None = None) -> tuple[Path, QMimeData]:
    """Create the WAV only when dragging starts; never remove a receiver's source."""
    rate = 44100
    samples = np.zeros((2 * rate, 2), dtype=np.float32)
    times = np.arange(round(0.18 * rate)) / rate
    pulse = (0.65 * np.sin(2 * np.pi * 80 * times) * np.exp(-30 * times)).astype(np.float32)
    for beat in range(4):
        start = round(beat * 0.5 * rate)
        samples[start : start + len(pulse), 0] = pulse
        samples[start : start + len(pulse), 1] = 0.8 * pulse

    # Keep successful and cancelled exports for inspection and delayed loading.
    directory = Path(tempfile.mkdtemp(prefix="chopper-dnd-probe-", dir=output_root))
    path = directory / "Chopper_probe_loop_120bpm_1bar.wav"
    export_segment(samples, rate, 0, 2, path)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
    return path.resolve(), mime


class DragHandle(QLabel):
    message = Signal(str)

    def __init__(self, output_root: Path | None = None, parent: QWidget | None = None):
        super().__init__("⠿  Drag this sample", parent)
        self._output_root = output_root
        self._press_position: QPoint | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(100)
        font = self.font()
        font.setPointSize(22)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Hold the left mouse button and drag to Bitwig or a folder in Dolphin.")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            distance = (event.position().toPoint() - self._press_position).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._press_position = None
                self.start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_position = None
        super().mouseReleaseEvent(event)

    def start_drag(self) -> None:
        try:
            path, mime = create_drag_payload(self._output_root)
            self.message.emit(f"WAV created: {path}\nOffered URI: {mime.urls()[0].toString()}")
            drag = QDrag(self)
            drag.setMimeData(mime)
            # Copy only: the target must never move or delete our exported source.
            action = drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
            self.message.emit(f"Qt result: {action.name}. File kept: {path.is_file()}")
            self.message.emit("Check the clip and sound: Qt's result does not guarantee a successful import.")
        except (OSError, RuntimeError, ValueError) as exc:
            self.message.emit(f"Drag-and-drop failed: {exc}")


class ProbeWindow(QWidget):
    def __init__(self, output_root: Path | None = None):
        super().__init__()
        self.setWindowTitle("Chopper — disposable drag-and-drop probe")
        self.resize(700, 460)
        self.handle = DragHandle(output_root, self)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        instructions = QLabel(
            "Test only: synthetic stereo loop, 2 seconds, 120 BPM, 24-bit WAV.\n"
            "Drag the handle to a Bitwig audio track, then to a folder in Dolphin.\n"
            "A file is created when each drag starts, not when this window opens.\n"
            "It stays on disk after a drop, cancellation or closing the probe.\n"
            "Use a test project: the system may clean up temporary files."
        )
        instructions.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(instructions)
        layout.addWidget(self.handle)
        layout.addWidget(self.log)
        self.handle.message.connect(self.report)
        self.report(
            f"Session: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}; "
            f"Actual Qt backend: {QApplication.platformName()}; "
            f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}"
        )
        self.report(f"Export root: {output_root or tempfile.gettempdir()}")
        self.report("Offered format: text/uri-list; allowed action: copy only.")

    def report(self, message: str) -> None:
        self.log.appendPlainText(message)
        print(message, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="Existing folder in which to keep test WAVs.")
    args = parser.parse_args()
    if args.output_root is not None and not args.output_root.is_dir():
        parser.error("--output-root must be an existing folder.")
    # Keep this disposable probe independent of the application's startup policy.
    app = QApplication([sys.argv[0]])
    window = ProbeWindow(args.output_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
