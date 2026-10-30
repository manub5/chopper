"""Scrollable sample rows mapped to the waveform's actual time-to-pixel transform."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QWidget

from choppeur.core.models import CandidateType
from choppeur.gui.lane_layout import CATEGORIES, LanePlacement, layout_samples
from choppeur.gui.presentation import format_time
from choppeur.gui.sample_state import SampleState
from choppeur.gui.waveform_view import WaveformView

_ROW_HEIGHT = 26
_HEADER_HEIGHT = 24


class SampleLanesView(QAbstractScrollArea):
    def __init__(self, state: SampleState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self._waveform: WaveformView | None = None
        self._placements: tuple[LanePlacement, ...] = ()
        self._tops: dict[int, int] = {}
        self._headers: list[tuple[str, int]] = []
        self._content_height = 0
        self._last_active: int | None = None
        self._pressed: tuple[QPointF, int | None, Qt.KeyboardModifier, list[float]] | None = None
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(100)
        self.viewport().setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())
        state.changed.connect(self._sync)
        self._sync()

    def link_time_axis(self, waveform: WaveformView) -> None:
        self._waveform = waveform
        # Reserve the same scrollbar gutter even when there are no overlapping rows.
        waveform.setViewportMargins(0, 0, self.verticalScrollBar().sizeHint().width(), 0)
        waveform.getViewBox().sigXRangeChanged.connect(lambda *_: self.viewport().update())
        waveform.getViewBox().sigResized.connect(lambda *_: self.viewport().update())
        self.viewport().update()

    def _sync(self) -> None:
        self._placements = layout_samples(self.state.items)
        self.setVisible(bool(self._placements))
        self._tops.clear()
        self._headers.clear()
        y = 0
        for category in CATEGORIES:
            group = [placement for placement in self._placements if placement.category == category]
            if not group:
                continue
            label = (
                "One-shots"
                if category[0] == "shot"
                else ("Boucles 1 mesure" if category[1] == 1 else "Boucles 1/2 mesure")
            )
            self._headers.append((label, y))
            y += _HEADER_HEIGHT
            for placement in group:
                self._tops[placement.item_id] = y + placement.row * _ROW_HEIGHT
            y += (max(placement.row for placement in group) + 1) * _ROW_HEIGHT + 6
        self._content_height = y
        self._update_scroll_range()
        if self.state.active_id != self._last_active:
            self._last_active = self.state.active_id
            if self._last_active is not None:
                self.reveal(self._last_active)
        self.viewport().update()

    def _update_scroll_range(self) -> None:
        self.verticalScrollBar().setRange(0, max(0, self._content_height - self.viewport().height()))
        self.verticalScrollBar().setPageStep(self.viewport().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scroll_range()

    def _time_x(self, seconds: float) -> float:
        if self._waveform is None:
            return 0.0
        waveform = self._waveform
        scene_point = waveform.getViewBox().mapViewToScene(QPointF(seconds, 0))
        # Keep fractional pixels; integer QWidget origins cancel separately.
        origin = self.viewport().mapFromGlobal(
            waveform.viewport().mapToGlobal(waveform.viewport().rect().topLeft())
        )
        viewport_point = waveform.viewportTransform().map(scene_point)
        return origin.x() + viewport_point.x()

    def sample_rect(self, item_id: int) -> QRectF:
        placement = next(p for p in self._placements if p.item_id == item_id)
        left = self._time_x(placement.start_seconds)
        right = self._time_x(placement.end_seconds)
        return QRectF(
            left, self._tops[item_id] - self.verticalScrollBar().value(), right - left, _ROW_HEIGHT - 2
        )

    def sample_tooltip(self, item_id: int) -> str:
        candidate = next(item.candidate for item in self.state.items if item.id == item_id)
        label = (
            "One-shot"
            if candidate.type is CandidateType.ONE_SHOT
            else ("Boucle 1 mesure" if candidate.bars == 1 else "Boucle 1/2 mesure")
        )
        tempo = f"{candidate.bpm:.1f} BPM" if candidate.bpm else "Tempo inconnu"
        return (
            f"{label}\n{tempo}\nDurée : {format_time(candidate.duration_seconds)}\n"
            f"Position : {format_time(candidate.start_seconds)}"
        )

    def reveal(self, item_id: int) -> None:
        if item_id not in self._tops:
            return
        bar = self.verticalScrollBar()
        top = self._tops[item_id]
        if top < bar.value():
            bar.setValue(top)
        elif top + _ROW_HEIGHT > bar.value() + self.viewport().height():
            bar.setValue(top + _ROW_HEIGHT - self.viewport().height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), self.palette().base())
        painter.setPen(self.palette().text().color())
        for label, y in self._headers:
            painter.drawText(
                QRectF(4, y - self.verticalScrollBar().value(), self.viewport().width() - 8, _HEADER_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        for placement in self._placements:
            rect = self.sample_rect(placement.item_id)
            if not rect.intersects(QRectF(self.viewport().rect())):
                continue
            color = QColor("#D99A64" if placement.category[0] == "loop" else "#7F98A8")
            if placement.item_id in self.state.marked_ids:
                color = color.lighter(125)
            color.setAlpha(220 if placement.item_id in self.state.marked_ids else 145)
            painter.setBrush(color)
            painter.setPen(
                QPen(
                    self.palette().highlight().color()
                    if placement.item_id == self.state.active_id
                    else color.darker(130),
                    2 if placement.item_id == self.state.active_id else 1,
                )
            )
            painter.drawRect(rect)
            if placement.item_id == self.state.playing_id:
                painter.setPen(self.palette().text().color())
                painter.drawText(rect.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, "▶")

    def _hit(self, point: QPointF) -> int | None:
        return next(
            (p.item_id for p in self._placements if self.sample_rect(p.item_id).contains(point)), None
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._waveform is not None:
            self._pressed = (
                event.position(),
                self._hit(event.position()),
                event.modifiers(),
                self._waveform.viewRange()[0][:],
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._pressed is not None and self._waveform is not None:
            position, _item_id, _modifiers, x_range = self._pressed
            dx = event.position().x() - position.x()
            if abs(dx) >= QApplication.startDragDistance():
                width = self._waveform.getViewBox().width()
                shift = -dx * (x_range[1] - x_range[0]) / max(width, 1)
                self._waveform.setXRange(x_range[0] + shift, x_range[1] + shift, padding=0)
        else:
            item_id = self._hit(event.position())
            self.viewport().setToolTip(self.sample_tooltip(item_id) if item_id is not None else "")

    def mouseReleaseEvent(self, event) -> None:
        if self._pressed is not None:
            position, item_id, modifiers, _x_range = self._pressed
            self._pressed = None
            if (
                event.position() - position
            ).manhattanLength() < QApplication.startDragDistance() and item_id is not None:
                self.state.click(item_id, bool(modifiers & Qt.KeyboardModifier.ControlModifier))
            event.accept()

    def wheelEvent(self, event) -> None:
        if self._waveform is not None:
            low, high = self._waveform.viewRange()[0]
            factor = math.exp(-max(-1200, min(1200, event.angleDelta().y())) / 600)
            center = (low + high) / 2
            half = max(0.0005, (high - low) * factor / 2)
            self._waveform.setXRange(center - half, center + half, padding=0)
            event.accept()
