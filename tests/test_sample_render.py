from dataclasses import replace

import numpy as np
import pytest

from chopper.core.models import Candidate, CandidateType


@pytest.mark.parametrize("rate, frames, frequencies", [(1.25, 6400, (500, 750)), (0.8, 10000, (320, 480))])
def test_record_player_speed_changes_duration_and_pitch(rate, frames, frequencies):
    from chopper.core.sample_render import render_candidate, rendered_frame_count

    t = np.arange(8000) / 8000
    audio = np.sin(2 * np.pi * t[:, None] * [400, 600]).astype(np.float32) * 0.5
    candidate = Candidate(CandidateType.ONE_SHOT, 0, 1, 1, bpm=120 * rate, source_bpm=120, playback_rate=rate)
    actual = render_candidate(audio, 8000, candidate)
    assert actual.shape == (frames, 2)
    assert rendered_frame_count(8000, 8000, candidate, channels=2) == frames
    bins = np.fft.rfftfreq(frames, 1 / 8000)
    assert tuple(bins[np.abs(np.fft.rfft(actual, axis=0)).argmax(axis=0)]) == pytest.approx(frequencies)
    np.testing.assert_array_equal(render_candidate(audio, 8000, replace(candidate, playback_rate=1)), audio)


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), 1e-8, 1e8])
def test_render_rejects_invalid_or_unusable_speed(rate):
    from chopper.core.sample_render import render_candidate

    candidate = Candidate(CandidateType.ONE_SHOT, 0, 1, 1, playback_rate=rate)
    with pytest.raises(ValueError):
        render_candidate(np.zeros(8000, dtype=np.float32), 8000, candidate)


def test_fractional_output_frames_match_the_duration_rule():
    from chopper.core.sample_render import render_candidate, rendered_frame_count

    candidate = Candidate(CandidateType.ONE_SHOT, 0, 0.003, 1, playback_rate=2)
    samples = np.zeros((3, 2), dtype=np.float32)
    assert rendered_frame_count(3, 1000, candidate, channels=2) == 2
    assert render_candidate(samples, 1000, candidate).shape == (2, 2)
