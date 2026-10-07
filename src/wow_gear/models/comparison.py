"""ComparisonResult: several items scored for one context, ranked, and the difference explained.

The explanation compares the two items that decide the recommendation - the best usable item
and the one it is measured against - component by component: "+36.0 from Strength into
attack power, +20.0 from crit, 0 from hit (2 of 2 beyond the cap)".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from wow_gear.models.enums import Stat
from wow_gear.models.score import ComponentKind, Confidence, ScoreResult

Outcome = Literal["winner", "tie", "only_usable", "none_usable", "single"]
"""winner: the best usable item scores clearly more than the next usable one. tie: the two
best usable items are within the tie margin. only_usable: one item is usable and is measured
against the best unusable one. none_usable: no item is usable. single: one item, scored."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExplanationLine(_Frozen):
    """One component of the difference between the two explained items: first minus second."""

    key: str
    label: str
    kind: ComponentKind
    stat: Stat | None = None
    first_amount: float
    """What the first item provides, in the stat's units (0 when it has none)."""
    second_amount: float
    first_value: float
    """The first item's contribution to its score."""
    second_value: float
    delta: float
    """first_value - second_value: positive favours the first item."""
    note: str | None = None
    """Why an amount counted only in part (a cap, an exclusive group), when one did."""
    text: str
    """The line as a phrase, such as "+20.0 from crit"."""


class Upgrade(_Frozen):
    """A candidate against the item it would replace, both measured from the same gear."""

    item_id: str
    item_name: str
    delta: float


class ComparisonResult(_Frozen):
    profile_id: str
    profile_version: str
    profile_label: str
    ruleset_id: str
    ruleset_version: str
    score_unit: str
    unit_abbreviation: str
    """The unit's short form, such as "AP" for "attack power equivalents (AP)"."""
    results: tuple[ScoreResult, ...]
    """Ranked: usable items first, then by score, each with ``rank`` and a label."""
    outcome: Outcome
    winner_id: str | None = None
    """The recommended item: set for "winner" and "only_usable"."""
    first_id: str | None = None
    """The two items the explanation compares (first minus second), when there are two."""
    second_id: str | None = None
    score_delta: float = 0.0
    """First item's score minus the second's."""
    headline: str
    why: str = ""
    """The largest component differences as one phrase."""
    lines: tuple[ExplanationLine, ...] = ()
    not_valued: tuple[str, ...] = ()
    """Stats on the explained items that this profile gives no value."""
    not_scored: tuple[str, ...] = ()
    """Effects and set memberships on the explained items that version 1 does not score."""
    replaced: ScoreResult | None = None
    """The equipped item, scored from the same gear as the candidates."""
    upgrades: tuple[Upgrade, ...] = ()
    notes: tuple[str, ...] = ()
    confidence: Confidence
    fingerprint: str

    def result(self, item_id: str) -> ScoreResult:
        return next(result for result in self.results if result.item_id == item_id)
