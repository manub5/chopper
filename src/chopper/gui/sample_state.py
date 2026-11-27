"""Shared selection, keep marks and playback requests, independent of the views."""

import math
from dataclasses import replace
from numbers import Real
from typing import Literal

from PySide6.QtCore import QObject, Signal, Slot

from chopper.core.models import Candidate, CandidateType
from chopper.core.sample_offset import adjust_candidate_bounds
from chopper.core.sample_render import rendered_frame_count
from chopper.gui.presentation import LoadedTrack, SampleItem, Window


class SampleState(QObject):
    changed = Signal()
    play_requested = Signal(int, int)
    range_play_requested = Signal(object, int)
    stop_requested = Signal()
    error_reported = Signal(str)

    def __init__(self, *, auto_play: bool = True, parent: QObject | None = None):
        super().__init__(parent)
        self._loaded_track: LoadedTrack | None = None
        self._items: tuple[SampleItem, ...] = ()
        self._ids: set[int] = set()
        self._active_id: int | None = None
        self._playing_id: int | None = None
        self._marked_ids: frozenset[int] = frozenset()
        self._auto_play = auto_play
        self._next_id = 0
        self._next_token = 0
        self._token: int | None = None
        self._requested_id: int | None = None
        self._range_window: Window | None = None
        self._requested_window: Window | None = None
        self._playing_window: Window | None = None
        self._stopping_token: int | None = None

    @property
    def loaded_track(self) -> LoadedTrack | None:
        return self._loaded_track

    @property
    def items(self) -> tuple[SampleItem, ...]:
        return self._items

    @property
    def active_id(self) -> int | None:
        return self._active_id

    @property
    def playing_id(self) -> int | None:
        return self._playing_id

    @property
    def marked_ids(self) -> frozenset[int]:
        return self._marked_ids

    @property
    def auto_play(self) -> bool:
        return self._auto_play

    @property
    def can_preview(self) -> bool:
        return self._range_window is not None or self._active_id is not None

    @property
    def has_playback(self) -> bool:
        return self._token is not None

    @property
    def playing_window(self) -> Window | None:
        return self._playing_window

    def load_track(self, loaded: LoadedTrack) -> None:
        self.clear()
        self._loaded_track = loaded
        self._set_items(loaded.candidates)
        self.changed.emit()

    def _set_items(self, candidates: tuple[Candidate, ...]) -> None:
        self._items = tuple(
            SampleItem(self._next_id + index, candidate) for index, candidate in enumerate(candidates)
        )
        self._next_id += len(self._items)
        self._ids = {item.id for item in self._items}

    def replace_candidates(self, candidates: tuple[Candidate, ...]) -> None:
        if self._loaded_track is None:
            return
        self.stop()
        self._loaded_track = replace(self._loaded_track, candidates=candidates)
        self._set_items(candidates)
        self._active_id = None
        self._marked_ids = frozenset()
        self.changed.emit()

    def set_boundary_offset(self, item_id: int, boundary: Literal["start", "end"], offset_ms: int) -> bool:
        loaded = self._loaded_track
        if loaded is None or item_id not in self._ids:
            return False
        index = next(index for index, item in enumerate(self._items) if item.id == item_id)
        item = self._items[index]
        start = offset_ms if boundary == "start" else item.start_offset_ms
        end = offset_ms if boundary == "end" else item.end_offset_ms
        bounds = adjust_candidate_bounds(
            loaded.candidates[index], start, end, loaded.sample_rate, len(loaded.samples)
        )
        candidate = replace(
            item.candidate, start_seconds=bounds.start_seconds, end_seconds=bounds.end_seconds
        )
        updated = SampleItem(item_id, candidate, start, end)
        return self._apply_sample_edit(index, updated, stop_preview=True)

    def sample_source_bpm(self, item_id: int) -> float | None:
        loaded = self._loaded_track
        if loaded is None or item_id not in self._ids:
            return None
        index = next(index for index, item in enumerate(self._items) if item.id == item_id)
        original = loaded.candidates[index]
        bpm = original.source_bpm
        if bpm is None and original.type is CandidateType.LOOP:
            bpm = original.bpm
        return bpm if bpm is not None and math.isfinite(bpm) and bpm > 0 else None

    def set_bpm(self, item_id: int, bpm: float, *, change_speed: bool = False) -> bool:
        if item_id not in self._ids:
            return False
        if not math.isfinite(bpm) or bpm <= 0:
            raise ValueError("BPM must be positive and finite.")
        index = next(index for index, item in enumerate(self._items) if item.id == item_id)
        item = self._items[index]
        source = self.sample_source_bpm(item_id)
        if change_speed and source is None:
            raise ValueError("A source BPM is required to change speed.")
        rate = bpm / source if change_speed and source is not None else item.candidate.playback_rate
        candidate = replace(item.candidate, bpm=bpm, source_bpm=source, playback_rate=rate)
        return self._apply_sample_edit(
            index, replace(item, candidate=candidate), stop_preview=rate != item.candidate.playback_rate
        )

    def _apply_sample_edit(self, index: int, updated: SampleItem, *, stop_preview: bool) -> bool:
        item = self._items[index]
        if updated == item:
            return True
        loaded = self._loaded_track
        if loaded is not None and updated.candidate.playback_rate != 1:
            channels = loaded.samples.shape[1] if loaded.samples.ndim == 2 else 1
            rendered_frame_count(
                len(loaded.samples), loaded.sample_rate, updated.candidate, channels=channels
            )
        if stop_preview and item.id in (self._requested_id, self._playing_id):
            self.stop()
        self._items = (*self._items[:index], updated, *self._items[index + 1 :])
        self.changed.emit()
        return True

    def select_range(self, window: Window, *, auto_preview: bool = True) -> None:
        loaded = self._loaded_track
        if loaded is None:
            return
        if (
            not isinstance(window, tuple)
            or len(window) != 2
            or any(not isinstance(t, Real) or isinstance(t, bool) or not math.isfinite(t) for t in window)
            or not 0 <= window[0] < window[1] <= len(loaded.samples) / loaded.sample_rate
        ):
            raise ValueError("Invalid preview range: expected 0 <= start < end <= audio duration.")
        self.stop()
        self._range_window = (float(window[0]), float(window[1]))
        self.changed.emit()
        if self._auto_play and auto_preview:
            self.toggle_playback()

    def clear_range(self) -> None:
        if self._range_window is None:
            return
        self.stop()
        self._range_window = None
        self.changed.emit()

    @Slot()
    def clear(self) -> None:
        self.stop()
        self._loaded_track = None
        self._items = ()
        self._ids.clear()
        self._active_id = None
        self._range_window = None
        self._marked_ids = frozenset()
        self.changed.emit()

    def click(self, item_id: int, control: bool = False) -> None:
        if item_id not in self._ids:
            return
        if control:
            self.toggle_mark(item_id)
            return
        self.navigate(item_id)
        if self._auto_play:
            self.toggle_playback()

    def navigate(self, item_id: int) -> None:
        if item_id not in self._ids or (item_id == self._active_id and self._range_window is None):
            return
        self.stop()
        self._active_id = item_id
        self._range_window = None
        self.changed.emit()

    def toggle_mark(self, item_id: int) -> None:
        if item_id not in self._ids:
            return
        self._marked_ids = self._marked_ids.symmetric_difference({item_id})
        self.changed.emit()

    @Slot()
    def mark_all(self) -> None:
        marks = frozenset(self._ids)
        if marks != self._marked_ids:
            self._marked_ids = marks
            self.changed.emit()

    @Slot()
    def clear_marks(self) -> None:
        if self._marked_ids:
            self._marked_ids = frozenset()
            self.changed.emit()

    @Slot(bool)
    def set_auto_play(self, enabled: bool) -> None:
        if enabled != self._auto_play:
            self._auto_play = enabled
            self.changed.emit()

    @Slot()
    def toggle_playback(self) -> None:
        if not self.can_preview:
            return
        if self._token is not None:
            self.stop()
            return
        self._next_token += 1
        self._token = self._next_token
        self._requested_window = self._range_window
        self._requested_id = self._active_id if self._requested_window is None else None
        if self._requested_window is not None:
            self.range_play_requested.emit(self._requested_window, self._token)
        else:
            self.play_requested.emit(self._requested_id, self._token)
        self.changed.emit()

    @Slot()
    def stop(self) -> None:
        if self._token is None:
            return
        # Invalidate before emitting: a connected player may finish synchronously.
        stopping_token = self._token
        self._token = None
        self._requested_id = None
        self._requested_window = None
        self._playing_id = None
        self._playing_window = None
        self._stopping_token = stopping_token
        try:
            self.stop_requested.emit()
        finally:
            self._stopping_token = None
        self.changed.emit()

    @Slot(int)
    def playback_started(self, token: int) -> None:
        if token == self._token:
            self._playing_id = self._requested_id
            self._playing_window = self._requested_window
            self.changed.emit()

    @Slot(int)
    def playback_finished(self, token: int) -> None:
        if token == self._token:
            self._token = None
            self._requested_id = None
            self._requested_window = None
            self._playing_id = None
            self._playing_window = None
            self.changed.emit()

    @Slot(int, str)
    def playback_failed(self, token: int, message: str) -> None:
        if token == self._token:
            self.playback_finished(token)
            self.error_reported.emit(message)
        elif token == self._stopping_token:
            # A synchronous stop error belongs to this command, not an old callback.
            self.error_reported.emit(message)
