"""BuildProfile: a class, role and build's priorities, as a small versioned research artifact.

A profile weights stats in one score unit (for example "attack power equivalents"), names
the conversions that turn primary stats into the stats it values, and states its caps,
soft caps and thresholds by referring to the ruleset's cap formulas - never by hard-coding a
mechanic. Every weight says where it came from (``basis`` and ``sources``).

Cross-checks against a ruleset (does the conversion exist, is the stat allowed) happen in
``wow_gear.profiles``, which loads profiles together with their ruleset.
"""

from __future__ import annotations

import math
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wow_gear.core.hashing import content_hash
from wow_gear.models.enums import (
    ClassName,
    ContentMode,
    Role,
    ShapeshiftForm,
    Stat,
    ValidationStatus,
    WeaponType,
)

SEMVER = r"^\d+\.\d+\.\d+$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRef(_Frozen):
    """A citation. ``retrieved`` is the date the value was read from the source."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_\-]*$")
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://")
    retrieved: date
    note: str | None = None


class WeightBasis(StrEnum):
    MECHANIC = "mechanic"
    """A game conversion, cited (for example 2 attack power per Strength)."""
    SOURCED = "sourced"
    """A valuation taken from a cited source (a guide, a simulation)."""
    DERIVED = "derived"
    """Computed from cited values by a documented calculation."""
    ASSUMPTION = "assumption"
    """A judgment no source supports; shown to the user as an assumption."""


class StatWeight(_Frozen):
    stat: Stat
    weight: float
    basis: WeightBasis
    note: str | None = None
    sources: tuple[str, ...] = ()

    @field_validator("weight")
    @classmethod
    def _finite(cls, weight: float) -> float:
        if not math.isfinite(weight):
            raise ValueError("a weight must be a finite number")
        return weight


class CapReference(_Frozen):
    """A cap value: a ruleset cap formula evaluated for the context, or a fixed number.

    ``reduced_by`` is what talents or the build already provide (for example 5 for a rogue
    with Precision against the hit cap): the gear cap is the formula's value minus it.
    """

    ruleset_cap: str | None = None
    fixed: float | None = None
    reduced_by: float = 0.0
    note: str | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> CapReference:
        if (self.ruleset_cap is None) == (self.fixed is None):
            raise ValueError("a cap is either a ruleset_cap or a fixed value")
        return self


class HardCap(_Frozen):
    """Beyond the cap the stat is worth nothing."""

    stat: Stat
    cap: CapReference
    note: str | None = None
    sources: tuple[str, ...] = ()


class SoftCap(_Frozen):
    """Beyond ``starts_at`` the stat is worth ``multiplier`` of its weight, until ``ends_at``."""

    stat: Stat
    starts_at: CapReference
    multiplier: float = Field(gt=0, lt=1)
    ends_at: CapReference | None = None
    note: str | None = None
    sources: tuple[str, ...] = ()


class Threshold(_Frozen):
    """A breakpoint: reaching it is worth ``bonus`` score points once."""

    stat: Stat
    at: CapReference
    label: str = Field(min_length=1)
    bonus: float
    basis: WeightBasis
    note: str | None = None
    sources: tuple[str, ...] = ()


class DerivedStatRule(_Frozen):
    """Values ``source`` through a ruleset conversion into ``target``.

    For example Agility into crit for a warrior: the ruleset holds how many Agility make 1%
    crit for the class, the profile holds what 1% crit is worth.
    """

    source: Stat
    target: Stat
    note: str | None = None

    @property
    def conversion(self) -> str:
        return f"{self.source}->{self.target}"


class ExclusiveGroup(_Frozen):
    """Stats that cannot all count at full value together: only the most valuable one counts."""

    stats: tuple[Stat, ...] = Field(min_length=2)
    mode: Literal["highest_only"] = "highest_only"
    note: str = Field(min_length=1)


class WeaponPreferences(_Frozen):
    preferred_types: tuple[WeaponType, ...] = ()
    note: str | None = None


class BuildProfile(_Frozen):
    """One build profile. See configs/profiles/README.md for the file format."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(pattern=SEMVER)
    label: str = Field(min_length=1)
    class_name: ClassName
    role: Role
    specialization: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    ruleset: str = Field(min_length=1)
    target_phase: int | None = Field(default=None, ge=1)
    target_level: int = Field(ge=1)
    default_content_mode: ContentMode
    shapeshift_form: ShapeshiftForm | None = None
    score_unit: str = Field(min_length=1)
    stat_weights: tuple[StatWeight, ...] = Field(min_length=1)
    derived_stats: tuple[DerivedStatRule, ...] = ()
    hard_caps: tuple[HardCap, ...] = ()
    soft_caps: tuple[SoftCap, ...] = ()
    thresholds: tuple[Threshold, ...] = ()
    exclusive_groups: tuple[ExclusiveGroup, ...] = ()
    weapon_preferences: WeaponPreferences = WeaponPreferences()
    proc_assumptions: tuple[str, ...] = ()
    set_bonus_rules: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    notes: str | None = None
    sources: tuple[SourceRef, ...] = ()
    validation_status: ValidationStatus

    @model_validator(mode="after")
    def _consistent(self) -> BuildProfile:
        weighted = [weight.stat for weight in self.stat_weights]
        duplicates = {stat for stat in weighted if weighted.count(stat) > 1}
        if duplicates:
            raise ValueError(f"stats weighted twice: {sorted(duplicates)}")
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        cited = {
            *(s for w in self.stat_weights for s in w.sources),
            *(s for c in self.hard_caps for s in c.sources),
            *(s for c in self.soft_caps for s in c.sources),
            *(s for t in self.thresholds for s in t.sources),
        }
        missing = cited - set(source_ids)
        if missing:
            raise ValueError(f"cited sources not listed under sources: {sorted(missing)}")
        for weight in self.stat_weights:
            if weight.basis in (WeightBasis.SOURCED, WeightBasis.MECHANIC) and not weight.sources:
                raise ValueError(f"the {weight.basis} weight for {weight.stat} cites no source")
        derived = [(rule.source, rule.target) for rule in self.derived_stats]
        if len(derived) != len(set(derived)):
            raise ValueError("a conversion is listed twice under derived_stats")
        for rule in self.derived_stats:
            if rule.source == rule.target:
                raise ValueError(f"{rule.source} cannot convert into itself")
        valued = {*weighted, *(rule.target for rule in self.derived_stats)}
        capped_stats = [cap.stat for cap in self.hard_caps] + [cap.stat for cap in self.soft_caps]
        for stat in capped_stats:
            if stat not in valued:
                raise ValueError(f"a cap on {stat}, which the profile does not value")
        hard = [cap.stat for cap in self.hard_caps]
        if len(hard) != len(set(hard)):
            raise ValueError("a stat has two hard caps")
        return self

    def weight_of(self, stat: Stat) -> float:
        return next((w.weight for w in self.stat_weights if w.stat == stat), 0.0)

    @property
    def content_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
