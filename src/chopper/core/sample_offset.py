from dataclasses import replace
from fractions import Fraction

from chopper.core.models import Candidate


def adjust_candidate_bounds(
    candidate: Candidate, start_offset_ms: int, end_offset_ms: int, sample_rate: int, frame_count: int
) -> Candidate:
    if type(start_offset_ms) is not int or type(end_offset_ms) is not int:
        raise ValueError("Enter a whole number of milliseconds.")
    start = round(candidate.start_seconds * sample_rate) + round(
        Fraction(start_offset_ms * sample_rate, 1000)
    )
    end = round(candidate.end_seconds * sample_rate) + round(Fraction(end_offset_ms * sample_rate, 1000))
    if not 0 <= start < end <= frame_count:
        raise ValueError("The sample must stay within the track and contain at least one audio frame.")
    return replace(
        candidate,
        start_seconds=start / sample_rate if start_offset_ms else candidate.start_seconds,
        end_seconds=end / sample_rate if end_offset_ms else candidate.end_seconds,
    )
