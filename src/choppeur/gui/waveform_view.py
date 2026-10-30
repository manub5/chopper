from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from choppeur.core.models import Candidate


def _downsample(samples: np.ndarray, max_points: int) -> np.ndarray:
    if len(samples) <= max_points:
        return samples
    factor = int(np.ceil(len(samples) / max_points))
    return samples[::factor]


class WaveformView(pg.PlotWidget):
    """Forme d'onde d'une piste, avec les marqueurs de début/fin des candidats."""

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
        self._playing_region = pg.LinearRegionItem(movable=False, brush=QColor(140, 160, 180, 50), pen=None)
        self._playing_region.setZValue(-1)
        self.addItem(self._playing_region, ignoreBounds=True)
        self._playing_region.hide()

    def set_downbeats(self, times: tuple[float, ...]) -> None:
        for line in self._downbeat_lines:
            self.removeItem(line)
        self._downbeat_lines = []
        for position in times:
            line = pg.InfiniteLine(pos=position, angle=90, pen=pg.mkPen(QColor(140, 140, 140, 80), width=1))
            self.addItem(line, ignoreBounds=True)
            self._downbeat_lines.append(line)

    def set_playing_candidate(self, candidate: Candidate | None) -> None:
        if self._playing_region is not None:
            if candidate is None:
                self._playing_region.hide()
            else:
                self._playing_region.setRegion((candidate.start_seconds, candidate.end_seconds))
                self._playing_region.show()
