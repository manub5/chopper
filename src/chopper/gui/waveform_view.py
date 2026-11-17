from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from chopper.core.models import Candidate
from chopper.gui.presentation import Window
from chopper.gui.selection_geometry import snap_window
from chopper.gui.selection_viewbox import SelectionViewBox
from chopper.gui.theme import LIGHT, ThemePalette


def _downsample(samples: np.ndarray, max_points: int) -> np.ndarray:
    if len(samples) <= max_points:
        return samples
    factor = int(np.ceil(len(samples) / max_points))
    return samples[::factor]


class WaveformView(pg.PlotWidget):
    """Waveform, manual region and passive playback highlight on a fixed y axis."""

    selection_finished = Signal(object)
    selection_invalidated = Signal()
    selection_clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        viewbox = SelectionViewBox()
        super().__init__(parent, viewBox=viewbox)
        self.setMenuEnabled(False)
        self.setLabel("bottom", "Time", units="s")
        self.showAxis("left", False)
        self.setMouseEnabled(x=True, y=False)
        self.plotItem.hideButtons()
        self._waveform_item: pg.PlotDataItem | None = None
        self._downbeat_lines: list[pg.InfiniteLine] = []
        self._playing_region: pg.LinearRegionItem | None = None
        self._selection_region: pg.LinearRegionItem | None = None
        self._selection: Window | None = None
        self._duration = 0.0
        self._downbeat_times: tuple[float, ...] = ()
        self._selection_enabled = True
        self._applying_region = False
        self._press_pos: QPointF | None = None
        self._press_time = 0.0
        self._press_selection: Window | None = None
        self._inside_at_press = False
        self._raw_selection: Window | None = None
        self._click_time: float | None = None
        self._dragging = False
        self._free = False
        self._native_source = ""
        self._drag_line: pg.InfiniteLine | None = None
        self._fixed_edge = 0.0
        self._gesture_id = 0
        self._finish_id = 0
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._finish_gesture)
        viewbox.draw_requested.connect(self._draw_region)
        viewbox.background_clicked.connect(self._background_clicked)
        viewbox.wheel_input.connect(
            lambda delta, shift, center: self.navigate_wheel(delta, shift=shift, center=center)
        )
        # PlotWidget installs a per-instance clear forwarder; expose our reset instead.
        self.__dict__.pop("clear", None)
        self.viewport().installEventFilter(self)
        self._theme = LIGHT
        self.apply_theme(self._theme)

    def apply_theme(self, palette: ThemePalette) -> None:
        self._theme = palette
        self.setBackground(palette.surface)
        axis = self.getAxis("bottom")
        axis.setPen(pg.mkPen(palette.secondary))
        axis.setTextPen(pg.mkPen(palette.secondary))
        axis.setLabel("Time", units="s", color=palette.secondary)
        if self._waveform_item is not None:
            self._waveform_item.setPen(pg.mkPen(palette.text, width=1))
        downbeat = QColor(palette.secondary)
        downbeat.setAlpha(65)
        for line in self._downbeat_lines:
            line.setPen(pg.mkPen(downbeat, width=1))
        if self._playing_region is not None:
            color = QColor(palette.playing)
            color.setAlpha(55)
            self._playing_region.setBrush(color)
        if self._selection_region is not None:
            color = QColor(palette.selection)
            color.setAlpha(95)
            self._selection_region.setBrush(color)
            for line in self._selection_region.lines:
                line.setPen(pg.mkPen(palette.active, width=1))
                line.setHoverPen(pg.mkPen(palette.active, width=2))

    @property
    def selection(self) -> Window | None:
        return self._selection

    def _cancel_gesture(self) -> None:
        self._finish_timer.stop()
        self._gesture_id += 1
        self._press_pos = None
        self._raw_selection = None
        self._dragging = False
        self._native_source = ""
        self._drag_line = None

    def clear(self) -> None:
        self._cancel_gesture()
        self._selection = None
        self._duration = 0.0
        self._downbeat_times = ()
        self._downbeat_lines = []
        self._selection_region = None
        self._playing_region = None
        self._waveform_item = None
        if self.plotItem is not None:
            self.plotItem.clear()

    def set_selection(self, window: Window | None) -> None:
        self._cancel_gesture()
        self._selection = None if window is None else snap_window(window, (), self._duration, free=True)
        self._display_region(self._selection)

    def set_selection_enabled(self, enabled: bool) -> None:
        self._selection_enabled = enabled
        self.getViewBox().selection_enabled = enabled
        if not enabled:
            self._cancel_gesture()
        if self._selection_region is not None:
            self._selection_region.setMovable(enabled)

    def _display_region(self, window: Window | None) -> None:
        region = self._selection_region
        if region is None:
            return
        self._applying_region = True
        try:
            if window is None:
                region.hide()
            else:
                values = window
                if (
                    self._drag_line is not None
                    and self._press_pos is not None
                    and self._raw_selection is not None
                ):
                    # Keep physical line identity when the moving edge crosses the fixed one.
                    moving, fixed = window if self._raw_selection[0] <= self._fixed_edge else window[::-1]
                    values = (moving, fixed) if self._drag_line is region.lines[0] else (fixed, moving)
                region.setRegion(values)
                region.show()
        finally:
            self._applying_region = False

    def _apply_raw_region(self, *, final: bool = False) -> None:
        if self._raw_selection is None:
            return
        self._selection = snap_window(
            self._raw_selection, self._downbeat_times, self._duration, free=self._free
        )
        display = self._selection
        if display is None and not final:
            display = snap_window(self._raw_selection, (), self._duration, free=True)
        self._display_region(display)

    def _draw_region(self, start: float, end: float, free: bool) -> None:
        if self._press_pos is not None and self._dragging and self._selection_enabled:
            self._native_source = "draw"
            self._free = free
            self._raw_selection = (start, end)
            self._apply_raw_region()

    def _background_clicked(self, seconds: float) -> None:
        if self._press_pos is not None:
            self._click_time = seconds

    def _native_region_changed(self, region) -> None:
        if self._applying_region or self._press_pos is None or not self._dragging:
            return
        if any(line.moving for line in region.lines):
            return
        self._native_source = "body"
        self._raw_selection = tuple(region.getRegion())
        self._apply_raw_region()

    def _line_dragged(self, line) -> None:
        region = self._selection_region
        if (
            region is not None
            and self._press_pos is not None
            and self._dragging
            and not self._applying_region
        ):
            self._native_source = "line"
            if self._drag_line is None:
                self._drag_line = line
                other = region.lines[1] if line is region.lines[0] else region.lines[0]
                self._fixed_edge = float(other.value())
            self._raw_selection = (float(line.value()), self._fixed_edge)
            self._apply_raw_region()

    def _native_region_finished(self, region) -> None:
        if self._applying_region or self._press_pos is None or not self._dragging:
            return
        if self._native_source != "line":
            self._raw_selection = tuple(region.getRegion())
            self._apply_raw_region()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Hide:
            self._cancel_gesture()
        if self.plotItem is None or not self._selection_enabled or self._duration <= 0:
            return super().eventFilter(watched, event)
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            scene_point = self.mapToScene(event.position().toPoint())
            if self.getViewBox().sceneBoundingRect().contains(scene_point):
                self._cancel_gesture()
                self._press_pos = QPointF(event.position())
                self._press_time = self.getViewBox().mapSceneToView(scene_point).x()
                self._press_selection = self._selection
                span = self.viewRange()[0][1] - self.viewRange()[0][0]
                margin = 5 * span / max(self.getViewBox().width(), 1)
                self._inside_at_press = self._selection is not None and (
                    self._selection[0] - margin <= self._press_time <= self._selection[1] + margin
                )
                self._click_time = None
                self._raw_selection = self._selection
        elif kind in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease) and self._press_pos is not None:
            self._free = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            if (event.position() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                self._dragging = True
            if kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._finish_id = self._gesture_id
                self._finish_timer.start(0)
        return super().eventFilter(watched, event)

    def _finish_gesture(self) -> None:
        if self._press_pos is None or self._finish_id != self._gesture_id:
            return
        if self._dragging:
            self._apply_raw_region(final=True)
            selection = self._selection
            self._press_pos = None
            self._dragging = False
            self._drag_line = None
            if selection is not None:
                self.selection_finished.emit(selection)
            else:
                self.selection_invalidated.emit()
        else:
            # pyqtgraph can move items before Qt's application drag threshold.
            self._display_region(self._selection)
            seconds = self._press_time if self._click_time is None else self._click_time
            outside = (
                self._press_selection is not None
                and not self._inside_at_press
                and not self._press_selection[0] <= seconds <= self._press_selection[1]
            )
            self._press_pos = None
            if outside:
                self.selection_clear_requested.emit()

    def pan_horizontal(self, delta_seconds: float) -> None:
        if self._duration > 0:
            self.getViewBox().translateBy(x=delta_seconds)

    def navigate_wheel(self, delta: float, *, shift: bool, center: float | None = None) -> None:
        if self._duration <= 0:
            return
        low, high = self.viewRange()[0]
        delta = max(-1200, min(1200, delta))
        if shift:
            self.pan_horizontal(-delta / 120 * (high - low) * 0.1)
        else:
            anchor = (low + high) / 2 if center is None else min(high, max(low, center))
            factor = math.exp(-delta / 600)
            scale = max(0.001 / max(high - low, 1e-12), factor)
            self.setXRange(anchor + (low - anchor) * scale, anchor + (high - anchor) * scale, padding=0)

    def set_waveform(self, samples: np.ndarray, sample_rate: int, *, max_points: int = 20_000) -> None:
        self.clear()
        # A manual zoom disables auto-ranging; reset it before attaching new data.
        self.enableAutoRange()

        display_samples = samples.mean(axis=1) if samples.ndim > 1 else samples
        downsampled = _downsample(display_samples, max_points)
        duration = len(samples) / sample_rate
        self._duration = duration
        if duration > 0:
            self.getViewBox().setLimits(xMin=0, xMax=duration, maxXRange=duration)
        times = np.linspace(0, duration, num=len(downsampled), endpoint=False)
        self._waveform_item = self.plot(times, downsampled, pen=pg.mkPen(width=1))
        self.autoRange(items=[self._waveform_item])
        if duration > 0:
            self.setXRange(0, duration, padding=0)
        self._playing_region = pg.LinearRegionItem(movable=False, pen=None)
        self._playing_region.setZValue(-1)
        self.addItem(self._playing_region, ignoreBounds=True)
        self._playing_region.hide()
        self._selection_region = pg.LinearRegionItem(
            values=(0.0, 0.0), bounds=(0.0, duration), movable=self._selection_enabled, swapMode="sort"
        )
        self._selection_region.setZValue(5)
        self.addItem(self._selection_region, ignoreBounds=True)
        self._selection_region.sigRegionChanged.connect(self._native_region_changed)
        self._selection_region.sigRegionChangeFinished.connect(self._native_region_finished)
        for line in self._selection_region.lines:
            line.sigDragged.connect(self._line_dragged)
        self._selection_region.hide()
        self.apply_theme(self._theme)

    def set_downbeats(self, times: tuple[float, ...]) -> None:
        for line in self._downbeat_lines:
            self.removeItem(line)
        self._downbeat_lines = []
        self._downbeat_times = tuple(t for t in times if math.isfinite(t))
        for position in self._downbeat_times:
            line = pg.InfiniteLine(pos=position, angle=90)
            self.addItem(line, ignoreBounds=True)
            self._downbeat_lines.append(line)
        self.apply_theme(self._theme)

    def set_playing_candidate(self, candidate: Candidate | None) -> None:
        if self._playing_region is not None:
            if candidate is None:
                self._playing_region.hide()
            else:
                self._playing_region.setRegion((candidate.start_seconds, candidate.end_seconds))
                self._playing_region.show()
