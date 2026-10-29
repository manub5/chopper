"""Track audio and stable sample identities shared by the interface views."""

from dataclasses import dataclass

import numpy as np

from choppeur.core.models import Analysis, Candidate


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
