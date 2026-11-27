import pytest

from chopper.core.models import Candidate, CandidateType


@pytest.mark.parametrize("offsets, bounds", [((-20, 30), (10143, 23373)), ((20, -30), (11907, 20727))])
def test_adjust_bounds_independently(offsets, bounds):
    from chopper.core.sample_offset import adjust_candidate_bounds

    original = Candidate(CandidateType.LOOP, 0.25, 0.5, 1, bpm=120, bars=0.25)
    adjusted = adjust_candidate_bounds(original, *offsets, 44100, 44100)
    assert (round(adjusted.start_seconds * 44100), round(adjusted.end_seconds * 44100)) == bounds
    assert adjusted.bpm == 120
    assert adjust_candidate_bounds(original, 0, 0, 44100, 44100) == original


@pytest.mark.parametrize("offsets", [(-1, 0), (0, 1), (100, 0), (101, 0)])
def test_adjust_bounds_rejects_invalid_pair(offsets):
    from chopper.core.sample_offset import adjust_candidate_bounds

    original = Candidate(CandidateType.ONE_SHOT, 0, 0.1, 1)
    with pytest.raises(ValueError):
        adjust_candidate_bounds(original, *offsets, 1000, 100)
