import time
from collections import Counter

import numpy as np
import pytest

from chopper.core import candidates
from chopper.core.models import CandidateType

SAMPLE_RATE = 22050


def _make_loopable_signal(duration_seconds=9.0, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)


def test_find_loop_candidates_respects_bar_alignment_and_duration():
    signal = _make_loopable_signal(duration_seconds=9.0)
    downbeat_times = (0.0, 2.0, 4.0, 6.0, 8.0)  # 120 BPM, 4 temps/mesure -> 2s/mesure

    result = candidates.find_loop_candidates(
        signal,
        SAMPLE_RATE,
        tempo_bpm=120.0,
        downbeat_times=downbeat_times,
        lengths_bars=(0.5, 1),
    )

    assert len(result) > 0
    duration = len(signal) / SAMPLE_RATE
    for candidate in result:
        assert candidate.type is CandidateType.LOOP
        assert candidate.bars in (0.5, 1)
        assert candidate.start_seconds in downbeat_times
        assert candidate.end_seconds <= duration + 1e-9
        assert candidate.bpm == 120.0

    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_find_loop_candidates_empty_without_enough_downbeats():
    signal = _make_loopable_signal(duration_seconds=2.0)
    assert candidates.find_loop_candidates(signal, SAMPLE_RATE, 120.0, (0.0,)) == []
    assert candidates.find_loop_candidates(signal, SAMPLE_RATE, 0.0, (0.0, 1.0)) == []


def _click_track(n_clicks=4, interval_seconds=0.5, sample_rate=SAMPLE_RATE):
    total_samples = int((n_clicks * interval_seconds + 0.5) * sample_rate)
    signal = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.01 * sample_rate)
    rng = np.random.default_rng(0)
    onset_times = []
    for i in range(n_clicks):
        start = int(i * interval_seconds * sample_rate)
        signal[start : start + click_len] += rng.uniform(-1.0, 1.0, click_len)
        onset_times.append(start / sample_rate)
    return signal, tuple(onset_times)


def test_find_one_shot_candidates_one_per_onset_with_short_duration():
    signal, onset_times = _click_track(n_clicks=4, interval_seconds=0.5)

    result = candidates.find_one_shot_candidates(signal, SAMPLE_RATE, onset_times, duration_seconds=0.4)

    assert len(result) == len(onset_times)
    for candidate in result:
        assert candidate.type is CandidateType.ONE_SHOT
        assert candidate.start_seconds in onset_times
        assert candidate.end_seconds > candidate.start_seconds
        assert candidate.duration_seconds <= 0.4 + 1e-9

    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_find_loop_candidates_stays_fast_on_a_very_long_track():
    """
    Un vrai bug de performance trouvé en revue de code : la recherche des
    downbeats dans la zone d'un candidat (régularité du tempo) refiltrait
    tout le tableau à chaque candidat, et le RMS global du morceau était
    recalculé à chaque candidat aussi (au lieu d'une fois). Sur un morceau
    de plusieurs heures (~1000 mesures ici, un DJ set en ferait bien plus),
    c'était quadratique : plusieurs dizaines de secondes à plusieurs minutes
    selon la taille. Après correctif (bisect + RMS global calculé une fois),
    ça reste de l'ordre de la seconde.
    """
    n_downbeats = 1000  # ~33 minutes à 120 BPM, mesures de 4 temps
    downbeat_times = tuple(2.0 * i for i in range(n_downbeats))
    duration_seconds = n_downbeats * 2.0 + 20
    samples = np.zeros(int(duration_seconds * SAMPLE_RATE), dtype=np.float32)

    start = time.monotonic()
    result = candidates.find_loop_candidates(
        samples, SAMPLE_RATE, 120.0, downbeat_times, lengths_bars=(0.5, 1)
    )
    elapsed = time.monotonic() - start

    assert len(result) > 0
    assert elapsed < 10.0, f"trop lent ({elapsed:.1f}s) : régression de performance probable"


def test_default_loops_quarter_half_and_one_bar_with_exact_durations():
    result = candidates.find_loop_candidates(np.ones(6000, dtype=np.float32), 1000, 120, (0.0, 2.0, 4.0))
    assert {c.bars for c in result} == {0.25, 0.5, 1.0}
    assert {(c.bars, c.duration_seconds) for c in result} == {(0.25, 0.5), (0.5, 1.0), (1.0, 2.0)}
    assert all(c.start_seconds in (0.0, 2.0, 4.0) for c in result)


@pytest.mark.parametrize("bars", [8, 3, 0, -0.5, float("nan"), True])
def test_engine_refuses_unsupported_loop_lengths(bars):
    with pytest.raises(ValueError):
        candidates.find_loop_candidates(np.ones(6000), 1000, 120, (0.0, 2.0), lengths_bars=(bars,))


@pytest.mark.parametrize("quota", [1, 8])
def test_each_length_keeps_its_own_quota_even_when_scores_compete(quota):
    # Repeated quiet tails favor the shorter lengths without mocking scoring.
    samples = np.tile(np.r_[np.ones(500), np.full(1500, 0.2)], 9)
    result = candidates.find_loop_candidates(
        samples, 1000, 120, tuple(float(t) for t in range(0, 18, 2)), max_candidates=quota
    )
    assert Counter(c.bars for c in result) == {0.25: quota, 0.5: quota, 1.0: quota}
    assert [c.score for c in result] == sorted((c.score for c in result), reverse=True)


def test_short_track_only_returns_lengths_that_fit():
    result = candidates.find_loop_candidates(np.ones(750), 1000, 120, (0.0, 2.0))
    assert len(result) == 1
    assert result[0].bars == 0.25
    assert result[0].end_seconds == 0.5


def test_repeated_length_does_not_multiply_quota():
    result = candidates.find_loop_candidates(
        np.ones(18000),
        1000,
        120,
        tuple(float(t) for t in range(0, 18, 2)),
        lengths_bars=(0.5, 0.5),
        max_candidates=1,
    )
    assert len(result) == 1
