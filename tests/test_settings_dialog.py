import pytest
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton

from chopper.core.settings import Settings
from chopper.gui.settings_dialog import SettingsDialog


def test_dialog_reflects_initial_settings(qapp):
    settings = Settings(export_format="flac", candidates_per_track=3, gpu_mode="cpu")
    dialog = SettingsDialog(settings)

    assert dialog._export_format.currentText() == "flac"
    assert dialog._candidates_per_track.value() == 3
    assert dialog._gpu_mode.currentText() == "CPU only"
    assert dialog._gpu_mode.currentData() == "cpu"


def test_settings_reads_back_edited_values(qapp):
    dialog = SettingsDialog(Settings())

    dialog._library_root.setText("/musique")
    dialog._export_dir.setText("/musique/export")
    dialog._export_format.setCurrentText("flac")
    for length, checkbox in dialog._loop_length_checks.items():
        checkbox.setChecked(length == 0.5)
    dialog._candidates_per_track.setValue(10)
    dialog._max_one_shot_seconds.setValue(3.5)
    dialog._gpu_mode.setCurrentIndex(dialog._gpu_mode.findData("cpu"))

    result = dialog.settings()

    assert result == Settings(
        library_root="/musique",
        export_dir="/musique/export",
        export_format="flac",
        loop_lengths_bars=(0.5,),
        candidates_per_track=10,
        max_one_shot_seconds=3.5,
        gpu_mode="cpu",
    )


def test_dialog_preserves_ui_preferences_when_editing_existing_controls(qapp):
    original = Settings(auto_play=False, force_dark=True)
    dialog = SettingsDialog(original)
    dialog._export_format.setCurrentText("flac")
    result = dialog.settings()
    assert result.auto_play is False
    assert result.force_dark is True
    assert result.export_format == "flac"
    assert result is not original
    assert original.export_format == "wav"


def test_loop_lengths_are_explicit_checkboxes(qapp):
    dialog = SettingsDialog(Settings())
    assert {length: check.text() for length, check in dialog._loop_length_checks.items()} == {
        1.0: "1 bar",
        0.5: "½ bar",
        0.25: "¼ bar",
    }
    assert all(check.isChecked() for check in dialog._loop_length_checks.values())
    assert dialog._candidates_per_track.maximum() == 64
    dialog._candidates_per_track.setValue(64)
    assert dialog.settings().candidates_per_track == 64


def test_force_dark_control_updates_only_its_preference(qapp):
    original = Settings(auto_play=False, force_dark=False, loop_lengths_bars=(0.5,))
    dialog = SettingsDialog(original)
    assert not dialog._force_dark.isChecked()
    dialog._force_dark.setChecked(True)
    result = dialog.settings()
    assert result.force_dark is True
    assert result.auto_play is False
    assert result.loop_lengths_bars == (0.5,)
    assert original.force_dark is False


@pytest.mark.parametrize(
    "lengths", [(0.25,), (0.5,), (1.0,), (0.25, 0.5), (0.25, 1.0), (0.5, 1.0), (0.25, 0.5, 1.0)]
)
def test_all_seven_choices_reopen_without_losing_selection(qapp, lengths):
    dialog = SettingsDialog(Settings(loop_lengths_bars=lengths))
    assert {length for length, check in dialog._loop_length_checks.items() if check.isChecked()} == set(
        lengths
    )
    dialog._export_format.setCurrentText("flac")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.settings().loop_lengths_bars == lengths
    reopened = SettingsDialog(dialog.settings())
    assert reopened.settings().loop_lengths_bars == lengths


def test_empty_loop_selection_cannot_accept(qapp, monkeypatch):
    dialog = SettingsDialog(Settings())
    for check in dialog._loop_length_checks.values():
        check.setChecked(False)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert warnings == ["Select at least one loop length."]


def test_settings_english_labels_and_automatic_device_roundtrip(qapp):
    dialog = SettingsDialog(Settings(gpu_mode="auto"))
    assert dialog.windowTitle() == "Settings"
    labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert {
        "Library folder",
        "Sample folder",
        "Export format",
        "Loop lengths",
        "Samples per category",
        "Max. one-shot length (s)",
        "Processing device",
        "Appearance",
    } <= labels
    assert dialog._force_dark.text() == "Force dark mode"
    assert [button.text() for button in dialog.findChildren(QPushButton)].count("Browse…") == 2
    assert dialog._gpu_mode.currentText() == "Automatic"
    assert dialog.settings().gpu_mode == "auto"
