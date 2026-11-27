"""Track audio and stable sample identities shared by the interface views."""

from dataclasses import dataclass

import numpy as np

from chopper.core.models import LOOP_LENGTHS_BARS, Analysis, Candidate, CandidateType, is_loop_length

Window = tuple[float, float]
_BAR_LABELS = {0.25: "¼ bar", 0.5: "½ bar", 1.0: "1 bar", 2.0: "2 bars", 4.0: "4 bars"}
LOOP_LENGTH_CHOICES = tuple((bars, _BAR_LABELS[bars]) for bars in LOOP_LENGTHS_BARS)


def format_time(seconds: float) -> str:
    """Round once to milliseconds before splitting, including minute carries."""
    total_ms = round(seconds * 1000)
    minutes, remainder = divmod(total_ms, 60_000)
    seconds_part, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds_part:02d}.{milliseconds:03d}"


def sample_type_label(candidate: Candidate) -> str:
    if candidate.type is CandidateType.ONE_SHOT:
        return "One-shot"
    bars = candidate.bars
    if bars is None or not is_loop_length(bars):
        raise ValueError("Unsupported loop length for display.")
    return {4.0: "4-bar loop", 2.0: "2-bar loop", 1.0: "1-bar loop", 0.5: "½-bar loop", 0.25: "¼-bar loop"}[
        bars
    ]


@dataclass(frozen=True)
class LoadedTrack:
    analysis: Analysis
    candidates: tuple[Candidate, ...]
    samples: np.ndarray
    sample_rate: int


@dataclass(frozen=True)
class CandidateSearchResult:
    request_id: int
    loaded: LoadedTrack
    window: Window | None
    length_bars: float | None
    message: str


@dataclass(frozen=True)
class SampleItem:
    id: int
    candidate: Candidate
    start_offset_ms: int = 0
    end_offset_ms: int = 0
