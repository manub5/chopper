"""Transactional manual selection state; dialogs and export stay at the boundary."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from chopper.core.models import is_loop_length
from chopper.gui.presentation import CandidateSearchResult, LoadedTrack, Window
from chopper.gui.sample_state import SampleState
from chopper.gui.selection_dialog import SelectionDecision


class SelectionController(QObject):
    changed = Signal()
    search_requested = Signal(int, object, object)

    def __init__(
        self,
        state: SampleState,
        *,
        choose: Callable[[str, bool], SelectionDecision],
        export_all: Callable[[], bool],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.state = state
        self._choose = choose
        self._export_all = export_all
        self._window: Window | None = None
        self._length_bars = 1.0
        self._result_window: Window | None = None
        self._result_length_bars: float | None = None
        self._result_message = ""
        self._status_message = ""
        self._next_request = 0
        self._pending: tuple[int, LoadedTrack, Window | None, float | None] | None = None
        self._confirming = False
        self._deferred: CandidateSearchResult | None = None

    @property
    def window(self) -> Window | None:
        return self._window

    @property
    def length_bars(self) -> float:
        return self._length_bars

    @property
    def result_window(self) -> Window | None:
        return self._result_window

    @property
    def result_length_bars(self) -> float | None:
        return self._result_length_bars

    @property
    def busy(self) -> bool:
        return self._pending is not None

    @property
    def locked(self) -> bool:
        return self.busy or self._confirming

    @property
    def status_message(self) -> str:
        return self._status_message

    def _update_status(self) -> None:
        self._status_message = (
            "Selection changed. Chop again to update samples."
            if self._result_window is not None
            and (self._window != self._result_window or self._length_bars != self._result_length_bars)
            else self._result_message
        )

    def set_selection(self, window: Window) -> None:
        if self.locked or self.state.loaded_track is None:
            return
        self.state.select_range(window)
        self._window = window
        self._update_status()
        self.changed.emit()

    def set_length(self, bars: float) -> None:
        if self.locked:
            return
        if not is_loop_length(bars):
            raise ValueError("Unsupported manual loop length.")
        if bars == self._length_bars:
            return
        self._length_bars = float(bars)
        if self.request_chop():
            return
        self._update_status()
        self.changed.emit()

    def invalidate_selection(self) -> None:
        if self.locked:
            return
        self.state.stop()
        self.state.clear_range()
        self._window = None
        self._update_status()
        self.changed.emit()

    def authorize_transition(self, action: str, *, include_region: bool = False) -> bool:
        if self._confirming or (self.busy and action != "close"):
            return False
        if self._result_window is None and not (include_region and self._window is not None):
            return True
        self.state.stop()
        can_export = self._result_window is not None and bool(self.state.items)
        self._confirming = True
        self.changed.emit()
        allowed = False
        try:
            decision = self._choose(action, can_export)
            allowed = decision is SelectionDecision.DISCARD or (
                decision is SelectionDecision.EXPORT and can_export and self._export_all()
            )
        finally:
            self._confirming = False
            self.changed.emit()
            deferred, self._deferred = self._deferred, None
            if not allowed and deferred is not None:
                self.apply_result(deferred)
        return allowed

    def _begin(self, window: Window | None, length: float | None) -> bool:
        loaded = self.state.loaded_track
        if self.locked or loaded is None:
            return False
        self.state.stop()
        self._next_request += 1
        self._pending = (self._next_request, loaded, window, length)
        self._status_message = "Finding samples…"
        self.changed.emit()
        self.search_requested.emit(self._next_request, window, length)
        return True

    def request_chop(self) -> bool:
        if self.locked or self._window is None or self.state.loaded_track is None:
            return False
        return self._begin(self._window, self._length_bars)

    def request_whole_track(self) -> bool:
        if self.locked or (self._window is None and self._result_window is None):
            return False
        return self.authorize_transition("whole track", include_region=True) and self._begin(None, None)

    def apply_result(self, result: CandidateSearchResult) -> bool:
        if self._pending is None:
            return False
        request_id, loaded, window, length = self._pending
        if (
            result.request_id != request_id
            or result.window != window
            or result.length_bars != length
            or self.state.loaded_track is not loaded
            or result.loaded.samples is not loaded.samples
            or result.loaded.analysis is not loaded.analysis
            or result.loaded.sample_rate != loaded.sample_rate
        ):
            return False
        if self._confirming:
            self._deferred = result
            return False
        self._pending = None
        self.state.replace_candidates(result.loaded.candidates)
        if window is None:
            self._window = None
            self.state.clear_range()
        self._result_window, self._result_length_bars = window, length
        self._result_message = self._status_message = result.message
        self.changed.emit()
        return True

    def fail(self, request_id: int, message: str) -> bool:
        if self._pending is None or self._pending[0] != request_id:
            return False
        self._pending = None
        self._deferred = None
        self._status_message = f"Search failed: {message}"
        self.changed.emit()
        return True

    def reset(self) -> None:
        if self._confirming:
            return
        self._pending = None
        self._deferred = None
        self._window = self._result_window = None
        self._result_length_bars = None
        self._result_message = self._status_message = ""
        self.state.clear_range()
        self.changed.emit()
