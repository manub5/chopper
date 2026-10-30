from choppeur.core.settings import Settings
from choppeur.gui.settings_dialog import SettingsDialog


def test_dialog_reflects_initial_settings(qapp):
    settings = Settings(export_format="flac", candidates_per_track=3, gpu_mode="cpu")
    dialog = SettingsDialog(settings)

    assert dialog._export_format.currentText() == "flac"
    assert dialog._candidates_per_track.value() == 3
    assert dialog._gpu_mode.currentText() == "cpu"


def test_settings_reads_back_edited_values(qapp):
    dialog = SettingsDialog(Settings())

    dialog._library_root.setText("/musique")
    dialog._export_dir.setText("/musique/export")
    dialog._export_format.setCurrentText("flac")
    dialog._loop_lengths_bars.setCurrentIndex(1)
    dialog._candidates_per_track.setValue(10)
    dialog._max_one_shot_seconds.setValue(3.5)
    dialog._gpu_mode.setCurrentText("cpu")

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


def test_loop_lengths_are_closed_choices(qapp):
    dialog = SettingsDialog(Settings())
    assert not dialog._loop_lengths_bars.isEditable()
    assert {dialog._loop_lengths_bars.itemData(i) for i in range(dialog._loop_lengths_bars.count())} == {
        (0.5, 1.0),
        (0.5,),
        (1.0,),
    }


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
