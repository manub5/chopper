from __future__ import annotations

from bisect import bisect_left, bisect_right
from numbers import Real

import numpy as np

from chopper.core.models import AUTO_LOOP_LENGTHS_BARS, Candidate, CandidateType, is_loop_length

DEFAULT_LOOP_LENGTHS_BARS = AUTO_LOOP_LENGTHS_BARS
DEFAULT_ONE_SHOT_DURATION_SECONDS = 2.0


def _rms(samples: np.ndarray) -> float:
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def _search_bounds(
    samples: np.ndarray, sample_rate: int, window: tuple[float, float] | None
) -> tuple[float, float, int, int]:
    duration = len(samples) / sample_rate
    if window is None:
        return 0.0, duration, 0, len(samples)
    if not isinstance(window, (tuple, list)) or len(window) != 2:
        raise ValueError("Invalid search window: expected (start, end) in seconds.")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in window):
        raise ValueError("Invalid search window: bounds must be finite numbers, not booleans.")
    start, end = window
    # This ordering also rejects NaN/infinity without converting huge integers.
    if not 0 <= start < end <= duration:
        raise ValueError("Invalid search window: require 0 <= start < end <= audio duration.")
    return float(start), float(end), round(start * sample_rate), round(end * sample_rate)


def _bar_duration(downbeat_times: tuple[float, ...]) -> float | None:
    if len(downbeat_times) < 2:
        return None
    return float(np.median(np.diff(downbeat_times)))


def _regularity_score(downbeat_times: np.ndarray, start: float, end: float) -> float:
    """1.0 = tempo parfaitement régulier sur la zone, 0.0 = très irrégulier.

    `downbeat_times` doit être trié (c'est le cas : beat_this les renvoie dans
    l'ordre chronologique). On y trouve la zone [start, end] par recherche
    dichotomique (bisect) plutôt qu'en filtrant tout le tableau à chaque appel :
    sur un morceau de plusieurs heures (des milliers de premiers temps de
    mesure), un filtre linéaire répété pour chaque candidat rendait l'analyse
    quadratique - plusieurs minutes au lieu de quelques secondes.
    """
    lo = bisect_left(downbeat_times, start)
    hi = bisect_right(downbeat_times, end)
    in_range = downbeat_times[lo:hi]
    if len(in_range) < 3:
        return 0.5  # pas assez de mesures dans la zone pour juger : score neutre
    intervals = np.diff(in_range)
    mean_interval = float(np.mean(intervals))
    if mean_interval <= 0:
        return 0.0
    coefficient_of_variation = float(np.std(intervals)) / mean_interval
    return float(np.clip(1.0 - coefficient_of_variation, 0.0, 1.0))


def _cut_smoothness_score(
    samples: np.ndarray, sample_rate: int, end_seconds: float, overall_rms: float, *, min_index: int = 0
) -> float:
    """Score haut si le niveau juste avant la coupure est faible (pas de coupure brutale).

    `overall_rms` est calculé une seule fois par l'appelant (pas ici) : le
    recalculer pour chaque candidat coûtait un parcours complet du signal à
    chaque fois, ce qui devenait très lent sur un morceau de plusieurs heures.
    """
    window = int(0.03 * sample_rate)  # 30 ms
    end_index = round(end_seconds * sample_rate)
    start_index = max(min_index, end_index - window)
    tail_rms = _rms(samples[start_index:end_index])
    ratio = tail_rms / overall_rms
    return float(np.clip(1.0 - ratio, 0.0, 1.0))


def find_loop_candidates(
    samples: np.ndarray,
    sample_rate: int,
    tempo_bpm: float,
    downbeat_times: tuple[float, ...],
    *,
    lengths_bars: tuple[float, ...] = DEFAULT_LOOP_LENGTHS_BARS,
    max_candidates: int = 8,
    window: tuple[float, float] | None = None,
) -> list[Candidate]:
    """Rank complete loops inside an optional absolute-time search window."""
    if any(not is_loop_length(bars) for bars in lengths_bars):
        raise ValueError("Only ¼-bar, ½-bar, 1-bar, 2-bar and 4-bar loops are supported.")
    bounds = _search_bounds(samples, sample_rate, window) if window is not None else None
    bar_duration = _bar_duration(downbeat_times)
    if bar_duration is None or tempo_bpm <= 0:
        return []

    lower, upper, first_index, last_index = bounds or _search_bounds(samples, sample_rate, None)
    if window is not None and last_index <= first_index:
        return []
    overall_rms = _rms(samples[first_index:last_index]) or 1e-9
    downbeat_array = np.asarray(downbeat_times, dtype=np.float64)
    candidates: list[Candidate] = []

    for bars in dict.fromkeys(lengths_bars):
        loop_duration = bar_duration * bars
        for start in downbeat_times:
            if window is not None and not lower <= start < upper:
                continue
            end = start + loop_duration
            if end > upper:
                continue

            start_index = round(start * sample_rate)
            end_index = round(end * sample_rate)
            if window is not None and end_index <= start_index:
                continue
            segment = samples[start_index:end_index]

            regularity = _regularity_score(downbeat_array, start, end)
            energy_score = float(np.clip(_rms(segment) / overall_rms, 0.0, 1.0))
            smoothness = _cut_smoothness_score(samples, sample_rate, end, overall_rms, min_index=first_index)
            score = 0.5 * regularity + 0.3 * energy_score + 0.2 * smoothness

            candidates.append(
                Candidate(
                    type=CandidateType.LOOP,
                    start_seconds=start,
                    end_seconds=end,
                    score=score,
                    bpm=tempo_bpm,
                    bars=bars,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    counts: dict[float | None, int] = {}
    selected = []
    for candidate in candidates:
        count = counts.get(candidate.bars, 0)
        if count < max_candidates:
            selected.append(candidate)
            counts[candidate.bars] = count + 1
    return selected


def find_one_shot_candidates(
    samples: np.ndarray,
    sample_rate: int,
    onset_times: tuple[float, ...],
    *,
    duration_seconds: float = DEFAULT_ONE_SHOT_DURATION_SECONDS,
    max_candidates: int = 8,
    window: tuple[float, float] | None = None,
) -> list[Candidate]:
    """Rank fixed-duration excerpts starting at cached onsets, clipped at the search boundary."""
    if not 0 < duration_seconds < float("inf"):
        raise ValueError("One-shot duration must be positive and finite.")
    lower, upper, _, _ = _search_bounds(samples, sample_rate, window)

    candidates: list[Candidate] = []
    for start in onset_times:
        if not lower <= start < upper:
            continue
        end = min(start + duration_seconds, upper)

        start_index = round(start * sample_rate)
        end_index = round(end * sample_rate)
        if end_index <= start_index:
            continue
        score = _rms(samples[start_index:end_index])

        candidates.append(
            Candidate(type=CandidateType.ONE_SHOT, start_seconds=start, end_seconds=end, score=score)
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]
