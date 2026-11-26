"""Explain durable exports and let the user choose their sample folder."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


def choose_export_folder(parent: QWidget, start: str = "") -> Path | None:
    box = QMessageBox(parent)
    box.setWindowTitle("Choose your sample folder")
    box.setText(
        "Choose where to keep exported samples and audio dragged into your DAW.\n"
        "You can change this folder in Settings at any time."
    )
    choose = box.addButton("Choose folder…", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    if box.clickedButton() != choose:
        return None
    directory = QFileDialog.getExistingDirectory(parent, "Choose your sample folder", start)
    return Path(directory) if directory else None
