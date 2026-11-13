import numpy as np
import pytest

from chopper.core.candidates import find_loop_candidates, find_one_shot_candidates
from chopper.core.models import CandidateType


def test_manual_long_loops_use_absolute_bounds_and_complete_lengths():
    samples = np.ones(16000)
    before = samples.copy()
    samples.setflags(write=False)
    loops = find_loop_candidates(
        samples,
        1000,
        120,
        tuple(float(t) for t in range(0, 17, 2)),
        lengths_bars=(2.0, 4.0),
        window=(2.0, 10.0),
    )
    assert {(c.bars, c.duration_seconds) for c in loops} == {(2.0, 4.0), (4.0, 8.0)}
    assert [(c.start_seconds, c.end_seconds) for c in loops if c.bars == 4.0] == [(2.0, 10.0)]
    assert all(2.0 <= c.start_seconds < c.end_seconds <= 10.0 for c in loops)
    np.testing.assert_array_equal(samples, before)


def test_selection_too_short_for_requested_loop_still_allows_shots():
    samples = np.ones(16000)
    assert (
        find_loop_candidates(samples, 1000, 120, (0.0, 2.0, 4.0, 6.0), lengths_bars=(4.0,), window=(2.0, 3.0))
        == []
    )
    shots = find_one_shot_candidates(samples, 1000, (1.0, 2.1, 2.5, 3.0), window=(2.0, 3.0))
    assert len(shots) == 2
    assert all(
        c.type is CandidateType.ONE_SHOT and 2.0 <= c.start_seconds < c.end_seconds <= 3.0 for c in shots
    )


@pytest.mark.parametrize(
    "window",
    [
        (float("nan"), 4.0),
        (2.0, float("nan")),
        (float("inf"), 4.0),
        (2.0, float("inf")),
        (True, 4.0),
        (2.0, False),
        (-1.0, 4.0),
        (2.0, 17.0),
        (4.0, 2.0),
        (2.0, 2.0),
        (2.0,),
        (2.0, 4.0, 6.0),
        "24",
        2.0,
        ("2", 4.0),
        (None, 4.0),
    ],
)
@pytest.mark.parametrize("kind", ["loop", "shot"])
def test_window_rejects_invalid_bounds(window, kind):
    with pytest.raises(ValueError, match="window"):
        if kind == "loop":
            find_loop_candidates(np.ones(16000), 1000, 120, (0.0, 2.0, 4.0, 6.0), window=window)
        else:
            find_one_shot_candidates(np.ones(16000), 1000, (1.0, 2.0, 3.0), window=window)


@pytest.mark.parametrize("kind", ["loop", "shot"])
def test_window_quota_is_applied_after_local_search(kind):
    samples = np.ones(64000)
    samples[40000:48000] = 0.1
    if kind == "loop":
        found = find_loop_candidates(
            samples,
            1000,
            120,
            tuple(float(t) for t in range(0, 65, 2)),
            lengths_bars=(1.0,),
            max_candidates=1,
            window=(40.0, 48.0),
        )
    else:
        found = find_one_shot_candidates(
            samples, 1000, (1.0, 3.0, 41.0, 43.0, 45.0, 47.0, 61.0), max_candidates=1, window=(40.0, 48.0)
        )
    assert len(found) == 1
    assert 40.0 <= found[0].start_seconds < found[0].end_seconds <= 48.0


@pytest.mark.parametrize("stereo", [False, True])
def test_scores_ignore_nonfinite_audio_outside_window(stereo):
    samples = np.full((12000, 2) if stereo else 12000, np.nan, dtype=np.float32)
    samples[2000:10000] = 0.2
    if stereo:
        samples[2000:10000, 1] = 0.4
    before = samples.copy()
    samples.setflags(write=False)
    loops = find_loop_candidates(
        samples, 1000, 120, (0.0, 2.0, 4.0, 6.0, 8.0, 10.0), lengths_bars=(2.0, 4.0), window=(2.0, 10.0)
    )
    shots = find_one_shot_candidates(samples, 1000, (1.0, 2.1, 4.2, 9.8, 10.5), window=(2.0, 10.0))
    assert loops and shots
    assert all(np.isfinite(c.score) and 2.0 <= c.start_seconds < c.end_seconds <= 10.0 for c in loops + shots)
    np.testing.assert_array_equal(samples, before)


def test_one_shot_silence_blocks_stop_at_window_end():
    samples = np.r_[np.ones(20), np.zeros(5), np.full(5, 100.0)]
    shots = find_one_shot_candidates(samples, 1000, (0.0,), window=(0.0, 0.025))
    assert len(shots) == 1
    assert shots[0].end_seconds == 0.020


def test_cut_smoothness_does_not_reach_before_search_window():
    samples = np.full(100, np.nan)
    samples[10:30] = 1.0
    loops = find_loop_candidates(
        samples, 1000, 24000, (0.0, 0.01, 0.02, 0.03, 0.04), lengths_bars=(0.25,), window=(0.01, 0.03)
    )
    assert loops
    assert all(np.isfinite(candidate.score) for candidate in loops)


def test_none_window_keeps_legacy_silence_scan():
    samples = np.r_[np.ones(20), np.zeros(5), np.full(5, 100.0)]
    shots = find_one_shot_candidates(
        samples, 1000, (0.0,), max_duration_seconds=0.025, silence_threshold_ratio=0.0001
    )
    assert len(shots) == 1 and shots[0].end_seconds == 0.025


def test_one_shot_at_end_is_excluded_and_last_shot_is_clipped():
    shots = find_one_shot_candidates(np.ones(6000), 1000, (1.0, 2.0, 3.7, 4.0, 5.0), window=(2.0, 4.0))
    assert [(c.start_seconds, c.end_seconds) for c in shots] == [(2.0, 3.7), (3.7, 4.0)]


def test_loop_uses_global_bar_metadata_for_short_window():
    loops = find_loop_candidates(
        np.ones(6000), 1000, 120, (0.0, 2.0, 4.0), lengths_bars=(0.25,), window=(2.0, 2.6)
    )
    assert [(c.start_seconds, c.end_seconds) for c in loops] == [(2.0, 2.5)]


@pytest.mark.parametrize("kind", ["loop", "shot"])
def test_subsample_window_yields_no_zero_frame_candidates(kind):
    samples = np.ones(1000)
    if kind == "loop":
        result = find_loop_candidates(
            samples, 1000, 120, (0.0, 0.0001, 0.0002), lengths_bars=(0.25,), window=(0.0, 0.0004)
        )
    else:
        result = find_one_shot_candidates(samples, 1000, (0.0,), window=(0.0, 0.0004))
    assert result == []


@pytest.mark.parametrize("kind", ["loop", "shot"])
def test_silent_window_has_finite_candidates_and_no_outside_bounds(kind):
    samples = np.zeros(6000)
    if kind == "loop":
        found = find_loop_candidates(samples, 1000, 120, (0.0, 2.0, 4.0), window=(2.0, 4.0))
    else:
        found = find_one_shot_candidates(samples, 1000, (2.0, 3.8), window=(2.0, 4.0))
    assert found
    assert all(np.isfinite(c.score) and 2.0 <= c.start_seconds < c.end_seconds <= 4.0 for c in found)


def test_rhythm_absent_does_not_block_cached_one_shots():
    assert find_loop_candidates(np.ones(6000), 1000, 0, (), window=(2.0, 4.0)) == []
    shots = find_one_shot_candidates(np.ones(6000), 1000, (2.0, 3.5), window=(2.0, 4.0))
    assert len(shots) == 2


def test_no_window_preserves_historical_lengths_and_scores():
    args = (np.ones(6000), 1000, 120, (0.0, 2.0, 4.0))
    found = find_loop_candidates(*args)
    assert found == find_loop_candidates(*args, window=None)
    assert len(found) == 9 and {c.bars for c in found} == {0.25, 0.5, 1.0}
    assert all(c.score == pytest.approx(0.55) for c in found)
