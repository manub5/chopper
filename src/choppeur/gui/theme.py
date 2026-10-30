"""Shared colors and native appearance tracking without overriding the system palette."""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class ThemePalette:
    dark: bool
    background: str
    surface: str
    text: str
    secondary: str
    active: str
    selection: str
    playing: str = "#F2C879"
    loop: str = "#D99A64"
    shot: str = "#7F98A8"
    sample_text: str = "#15191D"

    def sample_color(self, category: str, *, marked: bool) -> QColor:
        color = QColor(self.loop if category == "loop" else self.shot)
        color.setAlpha(255 if marked else 210)
        return color

    def to_qpalette(self) -> QPalette:
        palette = QPalette(QApplication.palette())
        roles = {
            QPalette.ColorRole.Window: self.background,
            QPalette.ColorRole.Base: self.surface,
            QPalette.ColorRole.AlternateBase: self.background,
            QPalette.ColorRole.WindowText: self.text,
            QPalette.ColorRole.Text: self.text,
            QPalette.ColorRole.Button: self.surface,
            QPalette.ColorRole.ButtonText: self.text,
            QPalette.ColorRole.ToolTipBase: self.surface,
            QPalette.ColorRole.ToolTipText: self.text,
            QPalette.ColorRole.PlaceholderText: self.secondary,
            QPalette.ColorRole.Highlight: self.selection,
            QPalette.ColorRole.HighlightedText: self.text,
            QPalette.ColorRole.Link: self.active,
        }
        for role, color in roles.items():
            palette.setColor(role, QColor(color))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(self.secondary))
        return palette


LIGHT = ThemePalette(False, "#F3F4F5", "#E9ECEF", "#2B3035", "#59616A", "#405D7A", "#D3DFEA")
DARK = ThemePalette(True, "#292B2E", "#32353A", "#E2E3E6", "#AEB4BC", "#AFC5DC", "#465C72")


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self, *, force_dark: bool = False, parent: QObject | None = None):
        super().__init__(parent)
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("ThemeManager nécessite une application Qt.")
        self._force_dark = force_dark
        self._scheme = QApplication.styleHints().colorScheme()
        # Never infer the system appearance from a forced child-widget palette.
        self._system_palette = QPalette(QApplication.palette())
        self.palette = self._choose_palette()
        QApplication.styleHints().colorSchemeChanged.connect(self._on_scheme_changed)
        app.installEventFilter(self)

    def _choose_palette(self) -> ThemePalette:
        if self._force_dark or self._scheme == Qt.ColorScheme.Dark:
            return DARK
        if self._scheme == Qt.ColorScheme.Light:
            return LIGHT
        background = self._system_palette.color(QPalette.ColorRole.Window)
        return DARK if background.lightnessF() < 0.5 else LIGHT

    def set_force_dark(self, enabled: bool) -> None:
        self._force_dark = enabled
        self._refresh()

    def _on_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        self._scheme = scheme
        self._refresh()

    def _refresh(self) -> None:
        palette = self._choose_palette()
        if palette != self.palette:
            self.palette = palette
            self.changed.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            system_palette = QPalette(QApplication.palette())
            if system_palette != self._system_palette:
                self._system_palette = system_palette
                self._refresh()
        return False
