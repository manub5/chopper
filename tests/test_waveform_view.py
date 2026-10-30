import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from choppeur.core.models import Candidate, CandidateType
from choppeur.gui.waveform_view import WaveformView

SAMPLE_RATE = 22050


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


def test_set_candidates_adds_two_marker_lines_per_candidate(qapp):
    view = WaveformView()
    view.set_waveform(np.zeros(1000, dtype=np.float32), SAMPLE_RATE)

    candidates = [
        Candidate(type=CandidateType.LOOP, start_seconds=0.0, end_seconds=1.0, score=1.0),
        Candidate(type=CandidateType.ONE_SHOT, start_seconds=2.0, end_seconds=2.2, score=0.5),
    ]

    view.set_candidates(candidates)

    assert len(view._marker_lines) == 4

    # Un second appel doit remplacer les marqueurs, pas les cumuler
    view.set_candidates(candidates[:1])
    assert len(view._marker_lines) == 2
