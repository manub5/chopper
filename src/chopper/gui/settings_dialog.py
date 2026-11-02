from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chopper.core.settings import Settings


class SettingsDialog(QDialog):
    """Fenêtre de paramètres (voir docs/SPEC.md « Paramètres »)."""

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self._initial_settings = replace(settings)

        self._library_root = QLineEdit(settings.library_root or "")
        self._export_dir = QLineEdit(settings.export_dir or "")

        self._export_format = QComboBox()
        self._export_format.addItems(["wav", "flac"])
        self._export_format.setCurrentText(settings.export_format)

        self._loop_length_checks: dict[float, QCheckBox] = {}
        loop_lengths_row = QHBoxLayout()
        for length, label in ((1.0, "1 bar"), (0.5, "½ bar"), (0.25, "¼ bar")):
            checkbox = QCheckBox(label)
            checkbox.setChecked(length in settings.loop_lengths_bars)
            self._loop_length_checks[length] = checkbox
            loop_lengths_row.addWidget(checkbox)

        self._candidates_per_track = QSpinBox()
        self._candidates_per_track.setRange(1, 8)
        self._candidates_per_track.setValue(settings.candidates_per_track)

        self._max_one_shot_seconds = QDoubleSpinBox()
        self._max_one_shot_seconds.setRange(0.1, 30.0)
        self._max_one_shot_seconds.setSingleStep(0.1)
        self._max_one_shot_seconds.setValue(settings.max_one_shot_seconds)

        self._gpu_mode = QComboBox()
        self._gpu_mode.addItems(["auto", "cpu"])
        self._gpu_mode.setCurrentText(settings.gpu_mode)
        self._force_dark = QCheckBox("Forcer sombre")
        self._force_dark.setChecked(settings.force_dark)

        form = QFormLayout()
        form.addRow(
            "Dossier racine de la bibliothèque",
            self._row_with_browse(self._library_root, self._browse_library_root),
        )
        form.addRow(
            "Dossier cible d'export", self._row_with_browse(self._export_dir, self._browse_export_dir)
        )
        form.addRow("Format d'export", self._export_format)
        form.addRow("Loop lengths", loop_lengths_row)
        form.addRow("Nombre de candidats par catégorie", self._candidates_per_track)
        form.addRow("Durée maximale d'un one-shot (s)", self._max_one_shot_seconds)
        form.addRow("Utilisation du GPU", self._gpu_mode)
        form.addRow("Apparence", self._force_dark)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _row_with_browse(line_edit: QLineEdit, on_browse) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(line_edit)
        button = QPushButton("Parcourir…")
        button.clicked.connect(on_browse)
        row.addWidget(button)
        return row

    def _browse_library_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier racine de la bibliothèque")
        if directory:
            self._library_root.setText(directory)

    def _browse_export_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Dossier cible d'export")
        if directory:
            self._export_dir.setText(directory)

    def accept(self) -> None:
        if not any(check.isChecked() for check in self._loop_length_checks.values()):
            QMessageBox.warning(self, "Loop lengths", "Select at least one loop length.")
            return
        super().accept()

    def settings(self) -> Settings:
        lengths = tuple(
            sorted(length for length, check in self._loop_length_checks.items() if check.isChecked())
        )
        return replace(
            self._initial_settings,
            library_root=self._library_root.text() or None,
            export_dir=self._export_dir.text() or None,
            export_format=self._export_format.currentText(),
            loop_lengths_bars=lengths,
            candidates_per_track=self._candidates_per_track.value(),
            max_one_shot_seconds=self._max_one_shot_seconds.value(),
            gpu_mode=self._gpu_mode.currentText(),
            force_dark=self._force_dark.isChecked(),
        )
