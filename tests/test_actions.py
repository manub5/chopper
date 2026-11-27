from types import SimpleNamespace

import pytest
import sounddevice as sd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from chopper.core.cache import AnalysisCache
from chopper.core.settings import Settings
from chopper.gui.main_window import MainWindow


@pytest.fixture
def window(qapp, tmp_path, loaded_track, monkeypatch):
    stream = SimpleNamespace(active=False)
    monkeypatch.setattr(sd, "play", lambda *args, **kwargs: setattr(stream, "active", True))
    monkeypatch.setattr(sd, "get_stream", lambda: stream)
    monkeypatch.setattr(sd, "stop", lambda **kwargs: setattr(stream, "active", False))
    result = MainWindow(
        Settings(export_dir=str(tmp_path / "exports")), AnalysisCache(tmp_path / "cache.sqlite")
    )
    result._on_track_analyzed(loaded_track)
    result.show()
    result.activateWindow()
    assert QTest.qWaitForWindowActive(result, 3000), "The compositor did not activate the test window"
    result.candidates_panel.table.setFocus()
    qapp.processEvents()
    yield result
    result.close()
    result.deleteLater()
    qapp.processEvents()


def key(widget, code, modifiers=Qt.KeyboardModifier.NoModifier):
    widget.window().activateWindow()
    assert QTest.qWaitForWindowActive(widget.window(), 3000)
    widget.setFocus()
    QApplication.processEvents()
    QTest.keyClick(widget, code, modifiers)
    QApplication.processEvents()


def test_mark_shortcut_toggles_only_active_and_is_not_ctrl_space(window):
    registry = window.action_registry
    state = window.sample_state
    state.navigate(state.items[1].id)
    table = window.candidates_panel.table
    key(table, Qt.Key.Key_M)
    assert state.marked_ids == {state.items[1].id}
    assert state.active_id == state.items[1].id and state.playing_id is None
    key(table, Qt.Key.Key_M)
    assert not state.marked_ids
    key(table, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    assert not state.marked_ids and state.playing_id is None
    assert registry.actions["mark"].shortcut().toString() == "M"


def test_shortcut_refresh_tolerates_destroyed_button(window):
    from PySide6.QtCore import QCoreApplication, QEvent

    button = window.chop_selection_button
    button.deleteLater()
    QCoreApplication.sendPostedEvents(button, QEvent.Type.DeferredDelete)
    registry = window.action_registry
    registry.set_available("chop_selection", False)
    assert not registry.actions["chop_selection"].isEnabled()


def test_space_and_escape_control_real_player_without_losing_marks(window):
    assert window.action_registry.actions["play"].isEnabled() is False
    state = window.sample_state
    state.navigate(state.items[0].id)
    state.toggle_mark(state.items[1].id)
    table = window.candidates_panel.table
    key(table, Qt.Key.Key_Space)
    assert state.playing_id == state.items[0].id
    key(table, Qt.Key.Key_Space)
    assert state.playing_id is None
    key(table, Qt.Key.Key_Space)
    key(table, Qt.Key.Key_Escape)
    assert state.playing_id is None
    assert state.marked_ids == {state.items[1].id}


def test_mark_all_and_clear_are_scoped_to_candidates(window):
    assert window.action_registry.actions["mark_all"].isEnabled()
    state = window.sample_state
    key(window.library_panel, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert not state.marked_ids
    table = window.candidates_panel.table
    key(table, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert state.marked_ids == {item.id for item in state.items}
    key(table, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert not state.marked_ids


@pytest.mark.parametrize("editor_type", [QLineEdit, QPlainTextEdit])
def test_candidate_shortcuts_do_not_steal_editor_input(window, editor_type, qapp):
    state = window.sample_state
    state.navigate(state.items[0].id)
    editor = editor_type(window.candidate_scope)
    editor.show()
    editor.setFocus()
    qapp.processEvents()
    QTest.keyClicks(editor, "m m")
    assert (editor.text() if isinstance(editor, QLineEdit) else editor.toPlainText()) == "m m"
    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert (
        editor.selectedText() if isinstance(editor, QLineEdit) else editor.textCursor().selectedText()
    ) == "m m"
    assert not state.marked_ids and state.playing_id is None
    assert not window.action_registry.actions["mark"].isEnabled()
    editor.close()


def test_modal_input_does_not_fire_main_window_shortcuts(window, qapp):
    state = window.sample_state
    state.navigate(state.items[0].id)
    dialog = QDialog(window)
    editor = QLineEdit(dialog)
    QVBoxLayout(dialog).addWidget(editor)
    observed = []

    def type_in_modal():
        editor.setFocus()
        qapp.processEvents()
        QTest.keyClicks(editor, "m m")
        observed.append((editor.text(), state.marked_ids, state.playing_id))
        dialog.accept()

    QTimer.singleShot(0, type_in_modal)
    dialog.exec()
    assert observed == [("m m", frozenset(), None)]
    qapp.processEvents()
    assert window.action_registry.actions["mark"].isEnabled(), (
        QApplication.activeModalWidget(),
        QApplication.focusWidget(),
        QApplication.activeWindow(),
    )
    key(window.candidates_panel.table, Qt.Key.Key_M)
    assert state.marked_ids == {state.items[0].id}


def test_empty_state_disables_candidate_actions_and_shortcuts_are_harmless(window):
    registry = window.action_registry
    window.sample_state.clear()
    for name in ("play", "stop", "mark", "mark_all", "clear_marks", "export_marked", "export_all"):
        assert not registry.actions[name].isEnabled()
    key(window.candidates_panel.table, Qt.Key.Key_M)
    key(window.candidates_panel.table, Qt.Key.Key_Space)
    assert not window.sample_state.marked_ids and window.sample_state.playing_id is None


def test_menus_help_and_buttons_share_the_same_actions(window):
    registry = window.action_registry
    menus = {action.text(): action.menu() for action in window.menuBar().actions()}
    assert set(menus) == {"File", "Playback", "Export", "Help"}
    assert registry.actions["mark"] in menus["Playback"].actions()
    assert registry.actions["analyze_album"] in menus["File"].actions()
    assert registry.actions["shortcuts"] in menus["Help"].actions()
    help_text = registry.help_text()
    for action in registry.actions.values():
        shortcut = action.shortcut().toString()
        if shortcut:
            assert shortcut in help_text and action.text() in help_text
    assert "Ctrl+Space" not in help_text
    assert registry.actions["play"].autoRepeat() is False
    for button in window.findChildren(QPushButton):
        bindings = [a for a in registry.actions.values() if a in button.actions()]
        if bindings and bindings[0].shortcut().toString():
            assert bindings[0].shortcut().toString() in button.toolTip()
    assert registry.actions["analyze_album"] in window.analyze_album_button.actions()


def test_export_shortcuts_and_buttons_write_exactly_once(window, tmp_path):
    assert isinstance(window.action_registry.actions["export_all"], QAction)
    state = window.sample_state
    state.toggle_mark(state.items[1].id)
    key(window.candidates_panel.table, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
    assert len(list((tmp_path / "exports").glob("*.wav"))) == 1
    window.candidates_panel.export_all_button.click()
    assert len(list((tmp_path / "exports").glob("*.wav"))) == 3
    key(
        window.candidates_panel.table,
        Qt.Key.Key_E,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert len(list((tmp_path / "exports").glob("*.wav"))) == 5


def test_album_action_and_button_stay_disabled_while_busy(window, tmp_path):
    window._on_folder_selected(tmp_path)
    action = window.action_registry.actions["analyze_album"]
    assert action.isEnabled() and window.analyze_album_button.isEnabled()
    window._set_busy(True)
    window.sample_state.toggle_mark(window.sample_state.items[0].id)
    assert not action.isEnabled() and not window.analyze_album_button.isEnabled()
    window._set_busy(False)
    window.sample_state.toggle_mark(window.sample_state.items[0].id)
    assert action.isEnabled() and window.analyze_album_button.isEnabled()


def test_holding_m_does_not_toggle_mark_repeatedly(window):
    from PySide6.QtCore import QEvent

    state = window.sample_state
    state.navigate(state.items[0].id)
    table = window.candidates_panel.table
    key(table, Qt.Key.Key_M)
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_M, Qt.KeyboardModifier.NoModifier, "m", True)
    QApplication.sendEvent(table, event)
    assert state.marked_ids == {state.items[0].id}


def test_f1_opens_help_from_registry_and_restores_actions(window, qapp):
    seen = []

    def inspect_help():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QDialog):
            seen.append((dialog.windowTitle(), [label.text() for label in dialog.findChildren(QLabel)]))
            dialog.reject()

    QTimer.singleShot(0, inspect_help)
    QTest.keyClick(window.candidates_panel.table, Qt.Key.Key_F1)
    qapp.processEvents()
    assert seen and seen[0][0] == "Keyboard shortcuts"
    assert window.action_registry.help_text() in seen[0][1]
    assert window.action_registry.actions["export_all"].isEnabled()


@pytest.mark.parametrize("view", ["sample_lanes", "waveform_view", "candidate_scope"])
def test_mark_shortcut_also_works_in_other_sample_views(window, view):
    state = window.sample_state
    state.navigate(state.items[1].id)
    key(getattr(window, view), Qt.Key.Key_M)
    assert state.marked_ids == {state.items[1].id}


def test_global_open_and_settings_shortcuts_work_from_library(window, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from chopper.gui.settings_dialog import SettingsDialog

    opened = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: opened.append(True) or "")
    key(window.library_panel, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    assert opened == [True]
    button = next(b for b in window.findChildren(QPushButton) if b.text() == "Open library…")
    button.click()
    assert opened == [True, True]
    settings = []
    monkeypatch.setattr(
        SettingsDialog, "exec", lambda self: settings.append(True) or QDialog.DialogCode.Rejected
    )
    key(window.library_panel, Qt.Key.Key_Comma, Qt.KeyboardModifier.ControlModifier)
    assert settings == [True]


def test_pending_action_refresh_is_cancelled_when_owner_is_deleted(qapp, monkeypatch):
    import sys

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QMainWindow, QWidget

    from chopper.gui.actions import ActionRegistry

    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, value, tb: errors.append(value))
    parent = QMainWindow()
    scope = QWidget(parent)
    registry = ActionRegistry(parent, scope)
    registry._focus_changed()
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert not errors
