"""Value curves: how much of an added amount counts, given caps and what is already there.

A curve says, for every total of a stat from gear, what fraction of one more point is
worth: nothing inside a dead zone, all of it up to the cap, a fraction of it in a soft-cap
band, nothing beyond. The amount of an item that counts is the area under that curve
between the total before the item and the total after it - so the same item counts fully
for one character and not at all for another who is already capped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ValueCurve:
    dead_zone: float = 0.0
    full_until: float = math.inf
    soft_multiplier: float = 0.0
    soft_until: float = math.inf

    def __post_init__(self) -> None:
        if not 0 <= self.dead_zone <= self.full_until <= self.soft_until:
            raise ValueError("a curve needs 0 <= dead_zone <= full_until <= soft_until")
        if not 0 <= self.soft_multiplier <= 1:
            raise ValueError("a soft-cap multiplier lies between 0 and 1")

    @property
    def is_flat(self) -> bool:
        return self.dead_zone == 0 and math.isinf(self.full_until)

    def area(self, total: float) -> float:
        """Value-weighted amount from 0 up to ``total`` (linear below 0)."""
        if total <= 0:
            return total if self.dead_zone == 0 else 0.0
        counted = max(0.0, min(total, self.full_until) - self.dead_zone)
        if total > self.full_until and self.soft_multiplier:
            counted += (min(total, self.soft_until) - self.full_until) * self.soft_multiplier
        return counted

    def counted(self, before: float, amount: float) -> float:
        """How much of ``amount``, added to ``before``, carries value."""
        return self.area(before + amount) - self.area(before)

    def segments(self, before: float, amount: float) -> CurveSegments:
        """Where ``amount`` lands on the curve: dead zone, full value, soft band, beyond.

        Signed like ``amount``: an item that lowers the stat gives negative segments.
        """
        sign = 1.0 if amount >= 0 else -1.0
        low, high = sorted((before, before + amount))

        def overlap(start: float, end: float) -> float:
            return max(0.0, min(high, end) - max(low, start))

        # Below zero counts in full on a curve without a dead zone, and not at all on one
        # with a dead zone - as ``area`` has it.
        below = overlap(-math.inf, 0.0)
        return CurveSegments(
            dead=sign * (overlap(0.0, self.dead_zone) + (below if self.dead_zone else 0.0)),
            full=sign
            * (overlap(self.dead_zone, self.full_until) + (0.0 if self.dead_zone else below)),
            soft=sign * overlap(self.full_until, self.soft_until) if self.soft_multiplier else 0.0,
            beyond=sign
            * (
                overlap(self.soft_until, math.inf)
                + (0.0 if self.soft_multiplier else overlap(self.full_until, self.soft_until))
            ),
        )


@dataclass(frozen=True)
class CurveSegments:
    """An amount split by where it lands on a value curve, in the stat's units."""

    dead: float
    full: float
    soft: float
    beyond: float


FLAT = ValueCurve()
