"""Pure time bounds and downbeat snapping for waveform gestures."""

import math
from bisect import bisect_left
from numbers import Real

from chopper.gui.presentation import Window


def snap_window(
    window: Window, downbeats: tuple[float, ...], duration: float, *, free: bool = False
) -> Window | None:
    if not math.isfinite(duration) or duration <= 0 or not all(math.isfinite(t) for t in window):
        return None
    start, end = sorted(min(duration, max(0.0, float(t))) for t in window)
    if not free:
        points = sorted(
            {
                float(t)
                for t in downbeats
                if isinstance(t, Real) and not isinstance(t, bool) and math.isfinite(t) and 0 <= t <= duration
            }
        )
        if points:

            def nearest(value: float) -> float:
                index = bisect_left(points, value)
                nearby = points[max(0, index - 1) : index + 1]
                return min(nearby, key=lambda t: (abs(t - value), t))

            start, end = nearest(start), nearest(end)
    return (start, end) if start < end else None
