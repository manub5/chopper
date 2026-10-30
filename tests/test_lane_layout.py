from dataclasses import replace

import pytest

from choppeur.core.models import Candidate, CandidateType
from choppeur.gui.presentation import SampleItem


def item(item_id, start, end, bars=1.0):
    return SampleItem(item_id, Candidate(CandidateType.LOOP, start, end, 1, bpm=120, bars=bars))


@pytest.mark.parametrize(
    "items, expected",
    [
        ((item(10, 0, 2), item(11, 1, 3), item(12, 2, 4)), {10: 0, 11: 1, 12: 0}),
        ((item(3, 0, 3), item(2, 0, 2), item(1, 0, 2)), {1: 0, 2: 1, 3: 2}),
        ((item(2, 1, 2), item(1, 0, 4), item(3, 1.5, 3)), {1: 0, 2: 1, 3: 2}),
    ],
)
def test_layout_never_occludes_and_is_independent_of_input_order(items, expected):
    from choppeur.gui.lane_layout import layout_samples

    placed = layout_samples(items)
    assert {p.item_id: p.row for p in placed} == expected
    assert placed == layout_samples(tuple(reversed(items)))
    assert len(placed) == len(items)


def test_layout_has_only_three_ordered_nonempty_categories():
    from choppeur.gui.lane_layout import layout_samples

    shot = SampleItem(3, Candidate(CandidateType.ONE_SHOT, 0, 0.2, 1))
    items = (shot, item(2, 0, 1, 0.5), item(1, 0, 2))
    assert [p.category for p in layout_samples(items)] == [("loop", 1.0), ("loop", 0.5), ("shot", 0.0)]
    assert [p.category for p in layout_samples((shot,))] == [("shot", 0.0)]
    assert layout_samples(()) == ()
    assert layout_samples((items[0],)) == layout_samples((replace(items[0]),))


def test_quarter_bar_lane_is_between_half_bars_and_shots():
    from choppeur.gui.lane_layout import layout_samples

    shot = SampleItem(4, Candidate(CandidateType.ONE_SHOT, 0, 0.2, 1))
    placed = layout_samples((shot, item(3, 0, 0.5, 0.25), item(2, 0, 1, 0.5), item(1, 0, 2)))
    assert [p.item_id for p in placed] == [1, 2, 3, 4]
