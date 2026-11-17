import pytest


def snap(window, downbeats=(0.0, 2.0, 4.0, 6.0), duration=8.0, *, free=False):
    from chopper.gui.selection_geometry import snap_window

    return snap_window(window, downbeats, duration, free=free)


def test_nearest_downbeats_and_alt_free_bounds():
    assert snap((1.1, 5.2)) == (2.0, 6.0)
    assert snap((1.1, 5.2), free=True) == (1.1, 5.2)


def test_ties_choose_earlier_downbeat_and_direction_is_normalized():
    assert snap((1.0, 5.0)) == (0.0, 4.0)
    assert snap((5.2, 1.1)) == (2.0, 6.0)


def test_bounds_and_missing_or_invalid_grid():
    assert snap((-3.0, 12.0), downbeats=()) == (0.0, 8.0)
    assert snap((1.1, 5.2), downbeats=(float("nan"), -1.0, float("inf"), 10.0)) == (1.1, 5.2)
    assert snap((1.1, 5.2), downbeats=(6.0, 2.0, 2.0, 0.0, 4.0)) == (2.0, 6.0)


@pytest.mark.parametrize(
    "window,duration",
    [
        ((0.2, 0.3), 8.0),
        ((2.0, 2.0), 8.0),
        ((-2.0, -1.0), 8.0),
        ((1.0, 2.0), 0.0),
        ((float("nan"), 2.0), 8.0),
        ((0.0, float("inf")), 8.0),
    ],
)
def test_collapsed_or_invalid_selection_is_not_invented(window, duration):
    assert snap(window, duration=duration) is None
