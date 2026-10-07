"""ScoreResult: the explainable result of evaluating one item for one context and profile.

A score is a sum of components, each one traceable to a stat, a conversion, a threshold or an
adjustment. Nothing is added to the total that is not listed as a component.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wow_gear.models.enums import Stat, ValidationStatus


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComponentKind(StrEnum):
    STAT = "stat"
    DERIVED = "derived"
    THRESHOLD = "threshold"
    WEAPON = "weapon"
    PROC = "proc"
    SET_BONUS = "set_bonus"
    CONTEXT = "context"


class ScoreComponent(_Frozen):
    """One line of the breakdown: an amount of something, valued at a weight."""

    key: str
    label: str
    kind: ComponentKind
    stat: Stat | None = None
    source_stat: Stat | None = None
    """For a derived component, the stat the amount was converted from."""
    amount: float
    """What the item provides, in the stat's units."""
    effective_amount: float
    """What counts after caps."""
    weight: float
    contribution: float
    note: str | None = None


class CapEvent(_Frozen):
    """A cap that reduced what an item's stat is worth."""

    stat: Stat
    cap_kind: Literal["hard", "soft"]
    cap: float
    before: float
    """Total from current gear before the item (the replaced item removed)."""
    after: float
    item_amount: float
    counted_amount: float
    wasted_amount: float
    message: str


class ThresholdEvent(_Frozen):
    """A breakpoint the item reaches, keeps or misses."""

    stat: Stat
    label: str
    threshold: float
    before: float
    after: float
    reached: bool
    bonus: float
    message: str


class ScoreWarning(_Frozen):
    code: str
    message: str
    severity: Literal["info", "warning"] = "warning"


class Confidence(_Frozen):
    level: Literal["high", "medium", "low"]
    reasons: tuple[str, ...] = ()


class ScoreResult(_Frozen):
    """The score of one item, with everything needed to explain and reproduce it."""

    item_id: str
    item_name: str
    item_version: str
    item_provider: str
    item_data_version: str
    score: float
    score_unit: str
    components: tuple[ScoreComponent, ...] = ()
    capped_stats: tuple[CapEvent, ...] = ()
    threshold_events: tuple[ThresholdEvent, ...] = ()
    warnings: tuple[ScoreWarning, ...] = ()
    assumptions: tuple[str, ...] = ()
    eligible: bool = True
    ineligibility: tuple[str, ...] = ()
    profile_id: str
    profile_version: str
    profile_hash: str
    ruleset_id: str
    ruleset_version: str
    ruleset_hash: str
    engine_version: str
    context_fingerprint: str
    validation_status: ValidationStatus
    confidence: Confidence
    rank: int | None = Field(default=None, ge=1)
    recommendation_label: str | None = None

    def component(self, key: str) -> ScoreComponent | None:
        return next((component for component in self.components if component.key == key), None)
