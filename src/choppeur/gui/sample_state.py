"""Shared selection, keep marks and playback requests, independent of the views."""

from PySide6.QtCore import QObject, Signal, Slot

from choppeur.gui.presentation import LoadedTrack, SampleItem


class SampleState(QObject):
    changed = Signal()
    play_requested = Signal(int, int)
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

    def load_track(self, loaded: LoadedTrack) -> None:
        self.clear()
        self._loaded_track = loaded
        self._items = tuple(
            SampleItem(self._next_id + index, candidate) for index, candidate in enumerate(loaded.candidates)
        )
        self._next_id += len(self._items)
        self._ids = {item.id for item in self._items}
        self.changed.emit()

    @Slot()
    def clear(self) -> None:
        self.stop()
        self._loaded_track = None
        self._items = ()
        self._ids.clear()
        self._active_id = None
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
        if item_id not in self._ids or item_id == self._active_id:
            return
        self.stop()
        self._active_id = item_id
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
        if self._active_id is None:
            return
        if self._token is not None:
            self.stop()
            return
        self._next_token += 1
        self._token = self._next_token
        self._requested_id = self._active_id
        self.play_requested.emit(self._active_id, self._token)

    @Slot()
    def stop(self) -> None:
        if self._token is None:
            return
        # Invalidate before emitting: a connected player may finish synchronously.
        stopping_token = self._token
        self._token = None
        self._requested_id = None
        self._playing_id = None
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
            self.changed.emit()

    @Slot(int)
    def playback_finished(self, token: int) -> None:
        if token == self._token:
            self._token = None
            self._requested_id = None
            self._playing_id = None
            self.changed.emit()

    @Slot(int, str)
    def playback_failed(self, token: int, message: str) -> None:
        if token == self._token:
            self.playback_finished(token)
            self.error_reported.emit(message)
        elif token == self._stopping_token:
            # A synchronous stop error belongs to this command, not an old callback.
            self.error_reported.emit(message)
