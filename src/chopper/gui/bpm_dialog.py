"""Edit a sample's BPM label or its playback speed."""

import math

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QWidget,
)

from chopper.gui.theme import ThemePalette


class BpmDialog(QDialog):
    def __init__(self, parent: QWidget, bpm: float | None, source_bpm: float | None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit sample BPM")
        self.value = QLineEdit("" if bpm is None else str(bpm))
        self.label_only = QRadioButton("BPM only")
        self.label_only.setChecked(True)
        self.change_speed = QRadioButton("Change speed")
        self.change_speed.setEnabled(source_bpm is not None)
        self.error = QLabel()
        self.result_value: tuple[float, bool] | None = None
        form = QFormLayout(self)
        form.addRow("BPM", self.value)
        form.addRow(self.label_only)
        form.addRow(self.change_speed)
        message = (
            "Changes duration and pitch, like a turntable."
            if source_bpm is not None
            else "No source BPM: only the label can be changed."
        )
        form.addRow(QLabel(message))
        form.addRow(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.value.selectAll()

    def accept(self) -> None:
        try:
            bpm = float(self.value.text().replace(",", "."))
            if not math.isfinite(bpm) or bpm <= 0:
                raise ValueError
        except ValueError:
            self.error.setText("Enter a positive, finite BPM.")
            self.value.setFocus()
            return
        self.result_value = bpm, self.change_speed.isEnabled() and self.change_speed.isChecked()
        super().accept()


def choose_bpm(
    parent: QWidget, bpm: float | None, source_bpm: float | None, palette: ThemePalette
) -> tuple[float, bool] | None:
    dialog = BpmDialog(parent, bpm, source_bpm)
    dialog.setPalette(palette.to_qpalette())
    palette.apply_control_styles(dialog)
    return dialog.result_value if dialog.exec() == QDialog.DialogCode.Accepted else None
