import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from chopper.gui.waveform_view import WaveformView


@pytest.fixture
def view(qapp):
    old_rate = pg.getConfigOption("mouseRateLimit")
    pg.setConfigOption("mouseRateLimit", 0)
    widget = WaveformView()
    widget.resize(900, 350)
    widget.set_waveform(np.tile([-0.5, 0.5], 4000), 1000)
    widget.set_downbeats((0.0, 2.0, 4.0, 6.0, 8.0))
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    pg.setConfigOption("mouseRateLimit", old_rate)


def point(view, seconds):
    return QPointF(view.mapFromScene(view.getViewBox().mapViewToScene(QPointF(seconds, 0))))


def mouse(
    view,
    kind,
    pos,
    button=Qt.MouseButton.NoButton,
    buttons=Qt.MouseButton.NoButton,
    modifiers=Qt.KeyboardModifier.NoModifier,
):
    event = QMouseEvent(
        kind, pos, QPointF(view.viewport().mapToGlobal(pos.toPoint())), button, buttons, modifiers
    )
    QApplication.sendEvent(view.viewport(), event)


def drag(
    view,
    start,
    end,
    *,
    button=Qt.MouseButton.LeftButton,
    start_mod=Qt.KeyboardModifier.NoModifier,
    end_mod=Qt.KeyboardModifier.NoModifier,
    flush=True,
):
    first, last = point(view, start), point(view, end)
    mouse(view, QEvent.Type.MouseMove, first)
    QApplication.processEvents()
    mouse(view, QEvent.Type.MouseButtonPress, first, button, button, start_mod)
    mouse(view, QEvent.Type.MouseMove, first + (last - first) * 0.5, buttons=button, modifiers=start_mod)
    mouse(view, QEvent.Type.MouseMove, last, buttons=button, modifiers=end_mod)
    mouse(view, QEvent.Type.MouseButtonRelease, last, button, modifiers=end_mod)
    if flush:
        QApplication.processEvents()


def click(view, seconds):
    pos = point(view, seconds)
    mouse(view, QEvent.Type.MouseMove, pos)
    QApplication.processEvents()
    mouse(view, QEvent.Type.MouseButtonPress, pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.LeftButton)
    QApplication.processEvents()


def wheel(view, delta, *, shift=False):
    center = view.viewport().rect().center()
    event = QWheelEvent(
        QPointF(center),
        QPointF(view.viewport().mapToGlobal(center)),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view.viewport(), event)
    QApplication.processEvents()


@pytest.mark.parametrize("start,end", [(1.1, 5.2), (5.2, 1.1)])
def test_drag_draws_snapped_region_without_panning_and_finishes_once(view, start, end):
    finished = []
    view.selection_finished.connect(finished.append)
    before = view.viewRange()
    drag(view, start, end)
    assert view.selection == (2.0, 6.0)
    assert finished == [(2.0, 6.0)]
    assert view.viewRange() == before


@pytest.mark.parametrize("start_alt,end_alt", [(False, True), (True, False), (True, True)])
def test_alt_modifiers_are_taken_from_end_of_gesture(view, start_alt, end_alt):
    finished = []
    view.selection_finished.connect(finished.append)
    alt = Qt.KeyboardModifier.AltModifier
    drag(
        view,
        1.1,
        5.2,
        start_mod=alt if start_alt else Qt.KeyboardModifier.NoModifier,
        end_mod=alt if end_alt else Qt.KeyboardModifier.NoModifier,
    )
    assert len(finished) == 1
    assert view.selection == pytest.approx((1.1, 5.2) if end_alt else (2.0, 6.0), abs=0.02)


@pytest.mark.parametrize(
    "start,end,expected", [(2.0, 0.8, (0.0, 4.0)), (4.0, 6.8, (2.0, 6.0)), (3.0, 4.9, (4.0, 6.0))]
)
def test_borders_and_body_share_snapping_and_completion(view, start, end, expected):
    view.set_selection((2.0, 4.0))
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, start, end)
    assert view.selection == expected
    assert finished == [expected]


def test_click_outside_requests_clear_without_removing_or_previewing(view):
    view.set_selection((2.0, 4.0))
    finished, cleared = [], []
    view.selection_finished.connect(finished.append)
    view.selection_clear_requested.connect(lambda: cleared.append(True))
    click(view, 3.0)
    assert not finished and not cleared
    click(view, 7.0)
    assert cleared == [True] and not finished
    assert view.selection == (2.0, 4.0)
    view.set_selection(None)
    assert view.selection is None and not finished


def test_background_drag_replaces_region_instead_of_requesting_clear(view):
    view.set_selection((2.0, 4.0))
    cleared = []
    view.selection_clear_requested.connect(lambda: cleared.append(True))
    drag(view, 5.1, 7.7)
    assert view.selection == (6.0, 8.0) and not cleared


def test_programmatic_changes_never_finish_a_gesture(view):
    finished = []
    view.selection_finished.connect(finished.append)
    view.set_selection((1.3, 3.8))
    view.set_downbeats((0.0, 4.0, 8.0))
    QApplication.processEvents()
    assert view.selection == (1.3, 3.8) and not finished


def test_collapsed_snap_has_no_finished_signal(view):
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, 0.1, 0.8)
    assert view.selection is None and not finished


def test_new_waveform_invalidates_old_pending_finish(view):
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, 1.1, 5.2, flush=False)
    view.set_waveform(np.ones(1000), 1000)
    QApplication.processEvents()
    assert view.selection is None and not finished


def test_clear_invalidates_selection_and_ignores_gestures_without_audio(view):
    view.set_selection((2.0, 4.0))
    view.clear()
    assert view.selection is None
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, 1.0, 5.0)
    assert view.selection is None and not finished


def test_disabled_selection_ignores_left_gestures_and_requests(view):
    view.set_selection((2.0, 4.0))
    view.set_selection_enabled(False)
    finished, cleared = [], []
    view.selection_finished.connect(finished.append)
    view.selection_clear_requested.connect(lambda: cleared.append(True))
    drag(view, 1.1, 5.2)
    click(view, 7.0)
    assert view.selection == (2.0, 4.0) and not finished and not cleared


def test_middle_shift_wheel_and_zoom_change_x_only(view):
    view.set_selection((2.0, 4.0))
    view.setXRange(2.0, 6.0, padding=0)
    y = view.viewRange()[1][:]
    drag(view, 4.0, 5.0, button=Qt.MouseButton.MiddleButton)
    low, high = view.viewRange()[0]
    assert low < 2.0 and high - low == pytest.approx(4.0)
    assert view.selection == (2.0, 4.0)
    before = view.viewRange()[0][:]
    wheel(view, -120, shift=True)
    after = view.viewRange()[0]
    assert after[0] > before[0] and after[1] - after[0] == pytest.approx(4.0)
    wheel(view, 120)
    zoomed = view.viewRange()[0]
    assert zoomed[1] - zoomed[0] < 4.0
    assert view.viewRange()[1] == y


def test_right_drag_cannot_scale_or_create_selection(view):
    before = view.viewRange()
    drag(view, 1.0, 6.0, button=Qt.MouseButton.RightButton)
    assert view.viewRange() == before and view.selection is None


@pytest.mark.parametrize("free", [False, True])
@pytest.mark.parametrize(
    "start,end,snapped,exact",
    [
        (2.0, 6.8, (4.0, 6.0), (4.0, 6.8)),
        (4.0, 0.8, (0.0, 2.0), (0.8, 2.0)),
    ],
)
def test_handle_crossing_keeps_opposite_edge_and_native_region_consistent(
    view, free, start, end, snapped, exact
):
    view.set_selection((2.0, 4.0))
    finished = []
    view.selection_finished.connect(finished.append)
    first, last = point(view, start), point(view, end)
    modifier = Qt.KeyboardModifier.AltModifier if free else Qt.KeyboardModifier.NoModifier
    mouse(view, QEvent.Type.MouseMove, first)
    QApplication.processEvents()
    mouse(
        view,
        QEvent.Type.MouseButtonPress,
        first,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        modifiers=modifier,
    )
    for step in range(1, 13):
        mouse(
            view,
            QEvent.Type.MouseMove,
            first + (last - first) * step / 12,
            buttons=Qt.MouseButton.LeftButton,
            modifiers=modifier,
        )
    mouse(view, QEvent.Type.MouseButtonRelease, last, Qt.MouseButton.LeftButton, modifiers=modifier)
    QApplication.processEvents()
    expected = exact if free else snapped
    assert view.selection == pytest.approx(expected, abs=0.025)
    assert view._selection_region.getRegion() == pytest.approx(expected, abs=0.025)
    assert len(finished) == 1 and finished[0] == pytest.approx(expected, abs=0.025)


@pytest.mark.parametrize("seconds", [2.0, 4.0, 3.0])
def test_subthreshold_handle_or_body_motion_restores_canonical_rectangle(view, seconds):
    view.set_selection((2.0, 4.0))
    finished = []
    view.selection_finished.connect(finished.append)
    first = point(view, seconds)
    distance = max(1, int(QApplication.startDragDistance() * 0.7))
    last = first + QPointF(distance, 0)
    mouse(view, QEvent.Type.MouseMove, first)
    QApplication.processEvents()
    mouse(view, QEvent.Type.MouseButtonPress, first, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseMove, last, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, last, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert view.selection == (2.0, 4.0)
    assert view._selection_region.getRegion() == (2.0, 4.0)
    assert not finished


@pytest.mark.parametrize(
    "start,end,expected", [(2.0, 1.1, (1.1, 4.0)), (4.0, 5.2, (2.0, 5.2)), (3.0, 4.1, (3.1, 5.1))]
)
def test_alt_on_handles_and_body_keeps_unsnapped_coordinates(view, start, end, expected):
    view.set_selection((2.0, 4.0))
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, start, end, end_mod=Qt.KeyboardModifier.AltModifier)
    assert len(finished) == 1
    assert view.selection == pytest.approx(expected, abs=0.025)


@pytest.mark.parametrize("reset", ["setter", "disable", "clear", "hide"])
def test_pending_finish_is_cancelled_by_ui_reset(view, reset):
    finished = []
    view.selection_finished.connect(finished.append)
    drag(view, 1.1, 5.2, flush=False)
    if reset == "setter":
        view.set_selection((2.0, 4.0))
    elif reset == "disable":
        view.set_selection_enabled(False)
    elif reset == "clear":
        view.clear()
    else:
        view.hide()
    QApplication.processEvents()
    assert not finished


def test_passive_playback_and_theme_changes_leave_selection_silent(view):
    from chopper.core.models import Candidate, CandidateType
    from chopper.gui.theme import DARK

    finished = []
    view.selection_finished.connect(finished.append)
    view.set_selection((2.0, 4.0))
    view.set_playing_candidate(Candidate(CandidateType.LOOP, 0.0, 2.0, 1.0, bpm=120, bars=1.0))
    view.apply_theme(DARK)
    view.resize(1100, 400)
    QApplication.processEvents()
    assert view.selection == (2.0, 4.0) and not finished
    assert view._playing_region is not view._selection_region


@pytest.mark.parametrize(
    "start,end,expected", [(1.1, 5.2, (1.1, 5.2)), (2.0, 1.1, (1.1, 4.0)), (3.0, 4.1, (3.1, 5.1))]
)
def test_alt_pressed_only_at_release_restores_raw_coordinates(view, start, end, expected):
    if start != 1.1:
        view.set_selection((2.0, 4.0))
    first, last = point(view, start), point(view, end)
    mouse(view, QEvent.Type.MouseMove, first)
    QApplication.processEvents()
    mouse(view, QEvent.Type.MouseButtonPress, first, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseMove, first + (last - first) * 0.5, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseMove, last, buttons=Qt.MouseButton.LeftButton)
    mouse(
        view,
        QEvent.Type.MouseButtonRelease,
        last,
        Qt.MouseButton.LeftButton,
        modifiers=Qt.KeyboardModifier.AltModifier,
    )
    QApplication.processEvents()
    assert view.selection == pytest.approx(expected, abs=0.025)
