from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


@pytest.mark.parametrize("action", ["cancel", "close", "picker-cancel", "choose"])
def test_folder_setup_returns_only_confirmed_path(qapp, tmp_path, monkeypatch, action):
    from choppeur.gui.export_folder_dialog import choose_export_folder

    destination = tmp_path / "Samples été"
    picker_calls = []

    def interact(box):
        assert box.windowTitle() == "Choose your sample folder"
        assert box.text() == (
            "Choose where to keep exported samples and audio dragged into your DAW.\n"
            "You can change this folder in Settings at any time."
        )
        buttons = {button.text(): button for button in box.buttons()}
        assert set(buttons) == {"Choose folder…", "Cancel"}
        assert box.defaultButton() is buttons["Cancel"]
        if action == "close":
            box.reject()
        else:
            buttons["Cancel" if action == "cancel" else "Choose folder…"].click()
        return box.result()

    def pick(parent, title, *args):
        assert title == "Choose your sample folder"
        picker_calls.append(True)
        return str(destination) if action == "choose" else ""

    monkeypatch.setattr(QMessageBox, "exec", interact)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", pick)
    parent = QWidget()
    try:
        result = choose_export_folder(parent)
        assert result == (Path(destination) if action == "choose" else None)
        assert picker_calls == ([] if action in {"cancel", "close"} else [True])
        assert not destination.exists()
    finally:
        parent.close()
