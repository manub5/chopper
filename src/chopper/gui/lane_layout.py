"""Deterministic interval placement, independent of Qt graphics."""

from dataclasses import dataclass

from chopper.core.models import CandidateType
from chopper.gui.presentation import SampleItem

CATEGORIES = (("loop", 4.0), ("loop", 2.0), ("loop", 1.0), ("loop", 0.5), ("loop", 0.25), ("shot", 0.0))


@dataclass(frozen=True)
class LanePlacement:
    item_id: int
    category: tuple[str, float]
    row: int
    start_seconds: float
    end_seconds: float


def layout_samples(items: tuple[SampleItem, ...]) -> tuple[LanePlacement, ...]:
    result = []
    for category in CATEGORIES:
        group = [
            item
            for item in items
            if (("loop", item.candidate.bars) if item.candidate.type is CandidateType.LOOP else ("shot", 0.0))
            == category
        ]
        ends: list[float] = []
        for item in sorted(group, key=lambda i: (i.candidate.start_seconds, i.candidate.end_seconds, i.id)):
            candidate = item.candidate
            row = next((index for index, end in enumerate(ends) if end <= candidate.start_seconds), len(ends))
            if row == len(ends):
                ends.append(candidate.end_seconds)
            else:
                ends[row] = candidate.end_seconds
            result.append(
                LanePlacement(item.id, category, row, candidate.start_seconds, candidate.end_seconds)
            )
    return tuple(result)
