"""Shared colors and local widget styling, with native appearance tracking."""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QPushButton, QWidget


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
    primary: str = "#0B57D0"
    on_primary: str = "#FFFFFF"
    control: str = "#E9EEF6"
    outline: str = "#747775"

    def sample_color(self, category: str, *, marked: bool) -> QColor:
        color = QColor(self.loop if category == "loop" else self.shot)
        color.setAlpha(255 if marked else 210)
        return color

    def widget_style_sheet(self) -> str:
        primary_hover = QColor(self.primary).darker(112).name() if not self.dark else "#C6DAFC"
        primary_pressed = QColor(self.primary).darker(126).name() if not self.dark else "#D3E3FD"
        # Keep the waveform and sample lanes on their own palette-driven rendering path.
        return f"""
            QPushButton, QLineEdit, QComboBox, QAbstractSpinBox {{
                background-color: {self.control};
                color: {self.text};
                border: 1px solid {self.outline};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton {{ border-radius: 14px; padding: 4px 12px; }}
            QPushButton:hover {{ background-color: {self.selection}; }}
            QPushButton:pressed {{ background-color: {self.selection}; border-color: {self.active}; }}
            QPushButton[materialPrimary="true"]:enabled {{
                background-color: {self.primary}; color: {self.on_primary};
                border: 2px solid transparent; font-weight: 600; padding: 3px 11px;
            }}
            QPushButton[materialPrimary="true"]:enabled:hover {{ background-color: {primary_hover}; }}
            QPushButton[materialPrimary="true"]:enabled:pressed {{ background-color: {primary_pressed}; }}
            QPushButton[materialPrimary="true"]:enabled:focus {{ border-color: {self.on_primary}; }}
            QPushButton:focus, QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{
                border-color: {self.active};
            }}
            QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
                background-color: {self.surface};
                border-color: {self.outline};
                color: {self.secondary};
            }}
            QAbstractSpinBox QLineEdit, QComboBox QLineEdit {{
                background-color: transparent;
                border: none;
                padding: 0;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.surface};
                color: {self.text};
                selection-background-color: {self.selection};
                selection-color: {self.text};
            }}
        """

    def apply_control_styles(self, parent: QWidget) -> None:
        # A sheet on the window would interrupt Qt's palette inheritance for unrelated widgets.
        sheet = self.widget_style_sheet()
        palette = self.to_qpalette()
        for kind in (QPushButton, QLineEdit, QComboBox, QAbstractSpinBox):
            for control in parent.findChildren(kind):
                if isinstance(control, QLineEdit) and isinstance(
                    control.parentWidget(), (QAbstractSpinBox, QComboBox)
                ):
                    continue
                if control.styleSheet() != sheet:
                    control.setStyleSheet(sheet)
                control.setPalette(palette)

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


LIGHT = ThemePalette(
    False,
    "#F8FAFD",
    "#F0F4F9",
    "#1F1F1F",
    "#444746",
    "#0B57D0",
    "#D3E3FD",
    playing="#FBBC04",
    loop="#4285F4",
    shot="#34A853",
)
DARK = ThemePalette(
    True,
    "#1F2024",
    "#282B30",
    "#ECEDEF",
    "#BAC0C8",
    "#A8C7FA",
    "#344963",
    playing="#FBBC04",
    loop="#8AB4F8",
    shot="#81C995",
    primary="#A8C7FA",
    on_primary="#062E6F",
    control="#34383D",
    outline="#8E918F",
)


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self, *, force_dark: bool = False, parent: QObject | None = None):
        super().__init__(parent)
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("ThemeManager requires a Qt application.")
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
