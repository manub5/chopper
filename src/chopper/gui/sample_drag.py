"""Native copy-only transfer of an already-created, permanent local file."""

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QWidget


def start_file_drag(source: QWidget, path: Path) -> Qt.DropAction:
    path = path.resolve(strict=True)
    if not path.is_file():
        raise OSError(f"Drag file is missing or unreadable: {path}")
    drag = QDrag(source)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    drag.setMimeData(mime)
    try:
        return drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
    finally:
        # Dispose only the Qt transfer object, never the durable WAV.
        drag.deleteLater()
