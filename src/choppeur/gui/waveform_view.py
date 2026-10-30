from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from choppeur.core.models import Candidate
from choppeur.gui.theme import LIGHT, ThemePalette


def _downsample(samples: np.ndarray, max_points: int) -> np.ndarray:
    if len(samples) <= max_points:
        return samples
    factor = int(np.ceil(len(samples) / max_points))
    return samples[::factor]


class WaveformView(pg.PlotWidget):
    """Waveform, downbeats and a passive highlight of the playing sample."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.setLabel("bottom", "Temps", units="s")
        self.showAxis("left", False)
        self.setMouseEnabled(x=True, y=False)
        self.plotItem.hideButtons()
        self._waveform_item: pg.PlotDataItem | None = None
        self._downbeat_lines: list[pg.InfiniteLine] = []
        self._playing_region: pg.LinearRegionItem | None = None
        self._theme = LIGHT
        self.apply_theme(self._theme)

    def apply_theme(self, palette: ThemePalette) -> None:
        self._theme = palette
        self.setBackground(palette.surface)
        axis = self.getAxis("bottom")
        axis.setPen(pg.mkPen(palette.secondary))
        axis.setTextPen(pg.mkPen(palette.secondary))
        axis.setLabel("Temps", units="s", color=palette.secondary)
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

    def set_waveform(self, samples: np.ndarray, sample_rate: int, *, max_points: int = 20_000) -> None:
        self.clear()
        self._downbeat_lines = []
        # A manual zoom disables auto-ranging; reset it before attaching new data.
        self.enableAutoRange()

        display_samples = samples.mean(axis=1) if samples.ndim > 1 else samples
        downsampled = _downsample(display_samples, max_points)
        duration = len(samples) / sample_rate
        times = np.linspace(0, duration, num=len(downsampled), endpoint=False)
        self._waveform_item = self.plot(times, downsampled, pen=pg.mkPen(width=1))
        self.autoRange(items=[self._waveform_item])
        self._playing_region = pg.LinearRegionItem(movable=False, pen=None)
        self._playing_region.setZValue(-1)
        self.addItem(self._playing_region, ignoreBounds=True)
        self._playing_region.hide()
        self.apply_theme(self._theme)

    def set_downbeats(self, times: tuple[float, ...]) -> None:
        for line in self._downbeat_lines:
            self.removeItem(line)
        self._downbeat_lines = []
        for position in times:
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
