"""Track audio and stable sample identities shared by the interface views."""

from dataclasses import dataclass

import numpy as np

from choppeur.core.models import Analysis, Candidate


def format_time(seconds: float) -> str:
    """Round once to milliseconds before splitting, including minute carries."""
    total_ms = round(seconds * 1000)
    minutes, remainder = divmod(total_ms, 60_000)
    seconds_part, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds_part:02d}.{milliseconds:03d}"


@dataclass(frozen=True)
class LoadedTrack:
    analysis: Analysis
    candidates: tuple[Candidate, ...]
    samples: np.ndarray
    sample_rate: int


@dataclass(frozen=True)
class SampleItem:
    id: int
    candidate: Candidate
