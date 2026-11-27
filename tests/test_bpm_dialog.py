import pytest
from PySide6.QtWidgets import QDialog, QWidget

from chopper.gui.bpm_dialog import BpmDialog
from chopper.gui.theme import DARK, LIGHT


@pytest.mark.parametrize("palette", [LIGHT, DARK])
@pytest.mark.parametrize("source", [None, 120.0])
def test_bpm_modes_and_validation(qapp, palette, source):
    parent = QWidget()
    dialog = BpmDialog(parent, None if source is None else 120.0, source)
    dialog.setPalette(palette.to_qpalette())
    palette.apply_control_styles(dialog)
    assert dialog.label_only.isChecked()
    assert dialog.change_speed.isEnabled() == (source is not None)
    dialog.value.setText("nan")
    dialog.accept()
    assert dialog.result_value is None and dialog.error.text()
    if source is not None:
        dialog.change_speed.click()
        assert not dialog.label_only.isChecked()
    dialog.value.setText("150,5")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_value == (150.5, source is not None)
