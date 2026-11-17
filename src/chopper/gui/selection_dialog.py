"""Safe default confirmation for transitions out of manual selection/results."""

from enum import Enum, auto

from PySide6.QtWidgets import QMessageBox, QWidget


class SelectionDecision(Enum):
    EXPORT = auto()
    DISCARD = auto()
    CANCEL = auto()


def confirm_selection_transition(parent: QWidget | None, action: str, can_export: bool) -> SelectionDecision:
    labels = {
        "whole track": ("Return to the whole track?", "Export and return", "Return without exporting"),
        "chop": ("Replace the manual samples?", "Export and chop", "Chop without exporting"),
        "track": ("Open another track?", "Export and open", "Open without exporting"),
        "album": ("Analyze the album?", "Export and analyze", "Analyze without exporting"),
        "close": ("Close Chopper?", "Export and close", "Close without exporting"),
    }
    title, export_label, discard_label = labels[action]
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText("Keep your manual samples before continuing?")
    box.setInformativeText(
        "Export saves all current manual samples, not just marked samples. Existing files are kept."
        if can_export
        else "No manual samples to export. Continuing removes the selection."
    )
    export_button = box.addButton(export_label, QMessageBox.ButtonRole.ActionRole)
    export_button.setEnabled(can_export)
    discard_button = box.addButton(discard_label, QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.setEscapeButton(cancel_button)
    try:
        box.exec()
        if box.clickedButton() is export_button and can_export:
            return SelectionDecision.EXPORT
        if box.clickedButton() is discard_button:
            return SelectionDecision.DISCARD
        return SelectionDecision.CANCEL
    finally:
        box.deleteLater()
