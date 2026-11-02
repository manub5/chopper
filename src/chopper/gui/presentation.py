"""Track audio and stable sample identities shared by the interface views."""

from dataclasses import dataclass

import numpy as np

from chopper.core.models import Analysis, Candidate, CandidateType, is_loop_length


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
        raise ValueError("Longueur de boucle non autorisée pour l'affichage.")
    return {1.0: "Boucle 1 mesure", 0.5: "Boucle 1/2 mesure", 0.25: "Boucle 1/4 de mesure"}[bars]


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
