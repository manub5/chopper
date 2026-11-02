from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from chopper.gui.sample_state import SampleState
from chopper.gui.waveform_view import WaveformView


@pytest.fixture
def lane_ui(qapp, loaded_track):
    from chopper.gui.sample_lanes import SampleLanesView

    window = QWidget()
    layout = QVBoxLayout(window)
    waveform = WaveformView()
    state = SampleState(auto_play=False)
    state.load_track(loaded_track)
    lanes = SampleLanesView(state)
    layout.addWidget(waveform)
    layout.addWidget(lanes)
    waveform.set_waveform(loaded_track.samples, 1000)
    lanes.link_time_axis(waveform)
    window.resize(800, 600)
    window.show()
    qapp.processEvents()
    yield window, waveform, state, lanes
    window.close()


def test_rectangles_click_ctrl_tooltip_and_nonediting(lane_ui, qapp):
    _, _waveform, state, lanes = lane_ui
    item_id = state.items[1].id
    rect = lanes.sample_rect(item_id)
    assert rect.height() >= 22
    QTest.mouseClick(lanes.viewport(), Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert state.active_id == item_id
    QTest.mouseClick(
        lanes.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        rect.center().toPoint(),
    )
    assert state.marked_ids == {item_id}
    assert lanes.sample_rect(item_id) == rect
    tip = lanes.sample_tooltip(item_id)
    assert "One-shot" in tip and "00:00.200" in tip and "00:01.000" in tip
    before = state.items
    QTest.mousePress(lanes.viewport(), Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    QTest.mouseMove(lanes.viewport(), rect.center().toPoint() + QPoint(40, 0))
    QTest.mouseRelease(
        lanes.viewport(), Qt.MouseButton.LeftButton, pos=rect.center().toPoint() + QPoint(40, 0)
    )
    assert state.items == before


def test_shared_time_axis_alignment_resize_pan_zoom_and_scroll(lane_ui, qapp, loaded_track):
    window, waveform, state, lanes = lane_ui
    duplicates = tuple(loaded_track.candidates[0] for _ in range(30))
    state.load_track(replace(loaded_track, candidates=duplicates))
    for width in (800, 1100, 700):
        window.resize(width, 600)
        qapp.processEvents()
        for x_range in ((0, 3), (0.4, 1.6), (0.0, 2.5)):
            waveform.setXRange(*x_range, padding=0)
            qapp.processEvents()
            rect = lanes.sample_rect(state.items[0].id)
            from PySide6.QtCore import QPointF

            point = waveform.mapFromScene(waveform.getViewBox().mapViewToScene(QPointF(0, 0)))
            expected = lanes.viewport().mapFromGlobal(waveform.viewport().mapToGlobal(point)).x()
            assert abs(rect.left() - expected) <= 1
    assert lanes.verticalScrollBar().maximum() > 0
    before = waveform.viewRange()[0][:]
    lanes.reveal(state.items[-1].id)
    assert lanes.sample_rect(state.items[-1].id).bottom() <= lanes.viewport().height()
    assert waveform.viewRange()[0] == before


def test_all_overlapping_samples_remain_clickable(lane_ui, loaded_track):
    _, _, state, lanes = lane_ui
    state.load_track(replace(loaded_track, candidates=(loaded_track.candidates[0],) * 5))
    for item in state.items:
        lanes.reveal(item.id)
        QTest.mouseClick(
            lanes.viewport(), Qt.MouseButton.LeftButton, pos=lanes.sample_rect(item.id).center().toPoint()
        )
        assert state.active_id == item.id


def test_lane_gestures_change_time_only_and_empty_state_hides_lanes(lane_ui, qapp):
    _, waveform, state, lanes = lane_ui
    before_x, before_y = waveform.viewRange()
    center = lanes.viewport().rect().center()
    wheel = QWheelEvent(
        QPointF(center),
        QPointF(lanes.viewport().mapToGlobal(center)),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(lanes.viewport(), wheel)
    qapp.processEvents()
    after_x, after_y = waveform.viewRange()
    assert after_x[1] - after_x[0] < before_x[1] - before_x[0]
    assert after_y == pytest.approx(before_y)
    assert lanes.verticalScrollBar().value() == 0
    state.clear()
    assert lanes.isHidden()


def test_lane_auto_second_click_stops_without_losing_mark(lane_ui):
    _, _, state, lanes = lane_ui
    state.set_auto_play(True)
    requests = []
    stops = []
    state.play_requested.connect(lambda item_id, token: requests.append((item_id, token)))
    state.stop_requested.connect(lambda: stops.append(True))
    item_id = state.items[0].id
    point = lanes.sample_rect(item_id).center().toPoint()
    QTest.mouseClick(lanes.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert requests[0][0] == item_id
    state.playback_started(requests[0][1])
    QTest.mouseClick(lanes.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, point)
    assert state.playing_id == item_id
    QTest.mouseClick(lanes.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert state.playing_id is None
    assert stops == [True]
    assert state.marked_ids == {item_id}


def test_quarter_bar_rectangle_is_clickable_and_labeled(lane_ui, loaded_track):
    _, _, state, lanes = lane_ui
    quarter = replace(loaded_track.candidates[0], bars=0.25, end_seconds=0.25)
    state.load_track(replace(loaded_track, candidates=(quarter,)))
    item_id = state.items[0].id
    QTest.mouseClick(
        lanes.viewport(), Qt.MouseButton.LeftButton, pos=lanes.sample_rect(item_id).center().toPoint()
    )
    assert state.active_id == item_id
    assert "Boucle 1/4 de mesure" in lanes.sample_tooltip(item_id)


def test_lane_zoom_out_and_drag_share_track_bounds(lane_ui, qapp):
    _, waveform, _, lanes = lane_ui
    center = lanes.viewport().rect().center()
    before_y = waveform.viewRange()[1][:]
    for _ in range(3):
        event = QWheelEvent(
            QPointF(center),
            QPointF(lanes.viewport().mapToGlobal(center)),
            QPoint(),
            QPoint(0, -1200),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(lanes.viewport(), event)
        qapp.processEvents()
        assert waveform.viewRange()[0] == pytest.approx([0, 3])
    for distance, expected in [(1000, (0, 1)), (-1000, (2, 3))]:
        waveform.setXRange(1, 2, padding=0)
        QTest.mousePress(lanes.viewport(), Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(lanes.viewport(), center + QPoint(distance, 0))
        QTest.mouseRelease(lanes.viewport(), Qt.MouseButton.LeftButton, pos=center + QPoint(distance, 0))
        qapp.processEvents()
        assert waveform.viewRange()[0] == pytest.approx(expected)
    assert waveform.viewRange()[1] == pytest.approx(before_y)
