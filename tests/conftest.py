import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from chopper.core.models import Analysis, Candidate, CandidateType, Track


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def loaded_track(tmp_path):
    from chopper.gui.presentation import LoadedTrack

    samples = np.column_stack([np.linspace(-0.2, 0.2, 3000), np.linspace(0.4, -0.4, 3000)]).astype(np.float32)
    track = Track(tmp_path / "source.wav", "Artist", "Album", "Title", 1, 3.0, 1000)
    analysis = Analysis(track, 120.0, (0.0, 0.5, 1.0), (0.0, 2.0))
    candidates = (
        Candidate(CandidateType.LOOP, 0.0, 1.0, 1.0, bpm=120.0, bars=1),
        Candidate(CandidateType.ONE_SHOT, 1.0, 1.2, 0.5),
    )
    return LoadedTrack(analysis, candidates, samples, 1000)
