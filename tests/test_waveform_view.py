import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from chopper.core.models import Candidate, CandidateType
from chopper.gui.waveform_view import WaveformView

SAMPLE_RATE = 22050


def wheel(view, delta):
    center = view.viewport().rect().center()
    event = QWheelEvent(
        QPointF(center),
        QPointF(view.viewport().mapToGlobal(center)),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view.viewport(), event)


def test_zoom_out_and_pan_never_leave_the_track(qapp):
    view = WaveformView()
    view.resize(800, 400)
    view.show()
    view.set_waveform(np.tile([-0.5, 0.5], 1500), 1000)
    qapp.processEvents()
    assert view.viewRange()[0] == pytest.approx([0, 3])
    y_range = view.viewRange()[1][:]
    for _ in range(3):
        wheel(view, -1200)
        qapp.processEvents()
        assert view.viewRange()[0] == pytest.approx([0, 3])
    view.setXRange(1, 2, padding=0)
    view.getViewBox().translateBy(x=-100)
    assert view.viewRange()[0] == pytest.approx([0, 1])
    view.getViewBox().translateBy(x=100)
    assert view.viewRange()[0] == pytest.approx([2, 3])
    assert view.viewRange()[1] == pytest.approx(y_range)
    view.close()


def test_loading_short_long_short_replaces_bounds_and_survives_resize(qapp):
    view = WaveformView()
    view.show()
    for duration in (1, 9, 2):
        view.set_waveform(np.tile([-0.5, 0.5], duration * 500), 1000)
        view.setXRange(-100, 100, padding=0)
        for width in (500, 900):
            view.resize(width, 400)
            qapp.processEvents()
            assert view.viewRange()[0] == pytest.approx([0, duration])
    view.close()


def test_waveform_locks_vertical_range_and_hides_auto_button(qapp):
    view = WaveformView()
    view.resize(800, 400)
    view.show()
    view.set_waveform(np.tile([-0.5, 0.5], 500), 1000)
    qapp.processEvents()
    vb = view.getViewBox()
    before = view.viewRange()[1][:]
    assert vb.state["mouseEnabled"] == [True, False]
    assert not view.plotItem.autoBtn.isVisible()
    center = view.viewport().rect().center()
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(view.viewport(), center + QPointF(80, 60).toPoint())
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=center + QPointF(80, 60).toPoint())
    vb.scaleBy((0.5, 1))
    qapp.processEvents()
    assert view.viewRange()[1] == pytest.approx(before)
    view.close()


def test_loading_waveform_resets_manual_scale_that_would_flatten_new_audio(qapp):
    view = WaveformView()
    view.resize(900, 400)
    view.show()
    samples = np.tile(np.array([-0.5, 0.5], dtype=np.float32), 500)
    view.set_waveform(samples, 1000)
    view.setRange(xRange=(100, 200), yRange=(-100, 100), padding=0)
    view.set_waveform(samples, 1000)
    qapp.processEvents()
    x_range, y_range = view.viewRange()
    assert y_range[0] <= -0.5 and 0.5 <= y_range[1] < 1
    assert y_range[1] - y_range[0] < 2
    assert x_range[0] <= 0 and 0.999 <= x_range[1] < 2
    view.close()


def test_stereo_waveform_is_only_a_display_projection(qapp):
    view = WaveformView()
    samples = np.column_stack([np.full(1000, 0.25), np.full(1000, -0.5)]).astype(np.float32)
    before = samples.copy()
    view.set_waveform(samples, 1000)
    x_data, y_data = view._waveform_item.getData()
    np.testing.assert_array_equal(y_data, np.full(1000, -0.125))
    assert x_data[-1] == 0.999
    np.testing.assert_array_equal(samples, before)


def test_set_waveform_plots_downsampled_data(qapp):
    view = WaveformView()
    samples = np.sin(np.linspace(0, 20, 50_000)).astype(np.float32)

    view.set_waveform(samples, SAMPLE_RATE, max_points=1_000)

    assert view._waveform_item is not None
    x_data, y_data = view._waveform_item.getData()
    assert len(x_data) <= 1_000
    assert len(x_data) == len(y_data)
    assert x_data[0] == 0.0


def test_set_waveform_keeps_short_signals_untouched(qapp):
    view = WaveformView()
    samples = np.zeros(100, dtype=np.float32)

    view.set_waveform(samples, SAMPLE_RATE, max_points=1_000)

    _, y_data = view._waveform_item.getData()
    assert len(y_data) == 100


def test_only_downbeats_and_passive_playback_highlight_remain(qapp):
    view = WaveformView()
    view.set_waveform(np.zeros(1000, dtype=np.float32), SAMPLE_RATE)

    candidate = Candidate(CandidateType.ONE_SHOT, 0.1, 0.2, 1)
    view.set_downbeats((0.0, 0.5))
    assert [line.value() for line in view._downbeat_lines] == [0.0, 0.5]
    view.set_playing_candidate(candidate)
    assert view._playing_region.getRegion() == (0.1, 0.2)
    assert not view._playing_region.movable
    view.set_playing_candidate(None)
    assert not view._playing_region.isVisible()
    view.set_downbeats(())
    assert not view._downbeat_lines
