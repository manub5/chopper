"""Throwaway native Qt drag-and-drop probe; not the future Choppeur interface."""

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
    directory = Path(tempfile.mkdtemp(prefix="choppeur-dnd-probe-", dir=output_root))
    path = directory / "Choppeur_probe_loop_120bpm_1bar.wav"
    export_segment(samples, rate, 0, 2, path)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path.resolve()))])
    return path.resolve(), mime


class DragHandle(QLabel):
    message = Signal(str)

    def __init__(self, output_root: Path | None = None, parent: QWidget | None = None):
        super().__init__("⠿  Glisser ce sample", parent)
        self._output_root = output_root
        self._press_position: QPoint | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(100)
        font = self.font()
        font.setPointSize(22)
        self.setFont(font)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Maintenir le clic gauche et glisser vers Bitwig ou un dossier dans Dolphin.")

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
            self.message.emit(f"WAV créé : {path}\nURI proposée : {mime.urls()[0].toString()}")
            drag = QDrag(self)
            drag.setMimeData(mime)
            # Copy only: the target must never move or delete our exported source.
            action = drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
            self.message.emit(f"Retour Qt : {action.name}. Fichier conservé : {path.is_file()}")
            self.message.emit("Vérifier le clip et le son : le retour Qt ne garantit pas l'import.")
        except (OSError, RuntimeError, ValueError) as exc:
            self.message.emit(f"Échec du glisser-déposer : {exc}")


class ProbeWindow(QWidget):
    def __init__(self, output_root: Path | None = None):
        super().__init__()
        self.setWindowTitle("Choppeur — prototype de glisser-déposer (jetable)")
        self.resize(700, 460)
        self.handle = DragHandle(output_root, self)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        instructions = QLabel(
            "Test uniquement : boucle synthétique stéréo, 2 secondes, 120 BPM, WAV 24 bits.\n"
            "Glisser la poignée vers une piste audio de Bitwig, puis vers un dossier dans Dolphin.\n"
            "Le fichier est créé au début de chaque glisser, pas au démarrage de cette fenêtre.\n"
            "Il reste sur disque après le dépôt, même annulé, et après fermeture du prototype.\n"
            "Utiliser un projet de test : le système peut nettoyer les fichiers temporaires."
        )
        instructions.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(instructions)
        layout.addWidget(self.handle)
        layout.addWidget(self.log)
        self.handle.message.connect(self.report)
        self.report(
            f"Session : {os.environ.get('XDG_SESSION_TYPE', 'non renseignée')} ; "
            f"backend Qt réel : {QApplication.platformName()} ; "
            f"bureau : {os.environ.get('XDG_CURRENT_DESKTOP', 'non renseigné')}"
        )
        self.report(f"Racine des exports : {output_root or tempfile.gettempdir()}")
        self.report("Formats proposés : text/uri-list ; action autorisée : copie uniquement.")

    def report(self, message: str) -> None:
        self.log.appendPlainText(message)
        print(message, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="Dossier existant pour conserver les WAV de test.")
    args = parser.parse_args()
    if args.output_root is not None and not args.output_root.is_dir():
        parser.error("--output-root doit être un dossier existant.")
    # Do not import app.py: its XCB fallback would bypass a native Wayland test.
    app = QApplication([sys.argv[0]])
    window = ProbeWindow(args.output_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
