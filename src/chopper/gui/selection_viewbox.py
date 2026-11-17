"""Waveform background gestures, leaving editable region handles to pyqtgraph."""

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal


class SelectionViewBox(pg.ViewBox):
    draw_requested = Signal(float, float, bool)
    background_clicked = Signal(float)
    wheel_input = Signal(float, bool, float)

    def __init__(self) -> None:
        super().__init__(enableMenu=False)
        self.selection_enabled = True
        self.setMouseMode(self.PanMode)
        self.setMouseEnabled(x=True, y=False)

    def mouseDragEvent(self, event, axis=None) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            if self.selection_enabled:
                start = self.mapSceneToView(event.buttonDownScenePos()).x()
                end = self.mapSceneToView(event.scenePos()).x()
                self.draw_requested.emit(
                    start, end, bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                )
        elif event.button() == Qt.MouseButton.MiddleButton:
            super().mouseDragEvent(event, axis=0)
        else:
            event.accept()

    def mouseClickEvent(self, event) -> None:
        event.accept()
        if self.selection_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.background_clicked.emit(self.mapSceneToView(event.scenePos()).x())

    def wheelEvent(self, event, axis=None) -> None:
        event.accept()
        self.wheel_input.emit(
            float(event.delta()),
            bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
            self.mapSceneToView(event.scenePos()).x(),
        )
