"""Shared actions, scoped Qt shortcuts and a help view derived from the registry."""

from html import escape

from PySide6.QtCore import QObject, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_SPECS = (
    ("open_library", "Open library…", "Ctrl+O", "File", False),
    ("analyze_album", "Analyze album", "", "File", False),
    ("settings", "Settings…", "Ctrl+,", "File", False),
    ("quit", "Quit", "Ctrl+Q", "File", False),
    ("play", "Preview / stop", "Space", "Playback", True),
    ("stop", "Stop preview / leave selection", "Esc", "Playback", False),
    ("chop_selection", "Chop selection", "C", "Playback", True),
    ("whole_track", "Whole track", "", "Playback", True),
    ("mark", "Mark / unmark active sample", "M", "Playback", True),
    ("mark_all", "Mark all samples", "Ctrl+A", "Playback", True),
    ("clear_marks", "Clear all marks", "Ctrl+Shift+A", "Playback", True),
    ("export_marked", "Export marked", "Ctrl+E", "Export", False),
    ("export_all", "Export all", "Ctrl+Shift+E", "Export", False),
    ("shortcuts", "Keyboard shortcuts", "F1", "Help", False),
)


def _is_editing(widget: QWidget | None) -> bool:
    while widget is not None:
        if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return True
        if isinstance(widget, QComboBox) and widget.isEditable():
            return True
        widget = widget.parentWidget()
    return False


class ActionRegistry(QObject):
    def __init__(self, window: QMainWindow, candidate_scope: QWidget):
        super().__init__(window)
        self.window = window
        self.actions: dict[str, QAction] = {}
        self._available: dict[str, bool] = {}
        self._candidate_ids: set[str] = set()
        self._buttons: dict[str, list[QPushButton]] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh)
        menus = {}
        for name, label, shortcut, menu_name, scoped in _SPECS:
            if menu_name not in menus:
                menus[menu_name] = window.menuBar().addMenu(menu_name)
            action = QAction(label, self)
            action.setAutoRepeat(False)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(
                Qt.ShortcutContext.WidgetWithChildrenShortcut if scoped else Qt.ShortcutContext.WindowShortcut
            )
            (candidate_scope if scoped else window).addAction(action)
            menus[menu_name].addAction(action)
            self.actions[name] = action
            self._available[name] = True
            if scoped or name == "stop":
                self._candidate_ids.add(name)
        self.actions["shortcuts"].triggered.connect(self.show_shortcuts)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._focus_changed)

    @Slot()
    def _focus_changed(self) -> None:
        self._refresh()
        # Modal teardown updates activeModalWidget after restoring focus.
        self._refresh_timer.start(0)

    def set_available(self, name: str, enabled: bool) -> None:
        self._available[name] = enabled
        self._refresh()

    def bind_button(self, button: QPushButton, name: str, *, connect_click: bool = True) -> None:
        action = self.actions[name]
        button.addAction(action)
        shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        button.setToolTip(f"{action.text()} ({shortcut})" if shortcut else action.text())
        if connect_click:
            button.clicked.connect(action.trigger)
        action.enabledChanged.connect(button.setEnabled)
        self._buttons.setdefault(name, []).append(button)
        button.setEnabled(action.isEnabled())

    @Slot()
    def _refresh(self) -> None:
        modal = QApplication.activeModalWidget() is not None
        editing = _is_editing(QApplication.focusWidget())
        for name, action in self.actions.items():
            enabled = self._available[name] and not modal and not (name in self._candidate_ids and editing)
            action.setEnabled(enabled)
            for button in self._buttons.get(name, ()):
                button.setEnabled(enabled)

    def help_text(self) -> str:
        rows = []
        for action in self.actions.values():
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            if shortcut:
                rows.append(f"<tr><td>{escape(action.text())}</td><td>{escape(shortcut)}</td></tr>")
        return "<table cellspacing='8'>" + "".join(rows) + "</table>"

    @Slot()
    def show_shortcuts(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Keyboard shortcuts")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.help_text()))
        note = QLabel(
            "Preview, chop and marking shortcuts work in the sample area. "
            "Esc stops preview and asks before leaving a selection. "
            "Shortcuts do not affect text fields or dialogs. "
            "Left-drag the waveform to select; drag edges or inside to adjust. "
            "Hold Alt for free selection. Middle-drag or Shift+wheel pans; wheel zooms."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
