"""Ruleset: one game version's mechanics, as configuration.

A ruleset file (``configs/rulesets/<id>.yaml``) holds what the game says - phases, level
range, class and race rules, the stats items may carry, stat conversions and the inputs of
each cap formula - and cites a source for every block. It holds no build priorities: those
belong to profiles.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wow_gear.core.hashing import content_hash
from wow_gear.models.enums import (
    ArmorType,
    ClassName,
    ContentMode,
    Faction,
    Race,
    RelicType,
    Stat,
    ValidationStatus,
    WeaponType,
)
from wow_gear.models.profile import SEMVER, SourceRef

CapKind = Literal[
    "melee_miss",
    "dual_wield_miss",
    "ranged_miss",
    "spell_miss",
    "defense_crit_immunity",
]
"""The cap formulas the calculations layer implements. A ruleset names caps of these kinds."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Cited(_Frozen):
    sources: tuple[str, ...] = Field(min_length=1)


class PhaseDef(_Cited):
    number: int = Field(ge=1)
    label: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ContentModeDef(_Cited):
    mode: ContentMode
    label: str = Field(min_length=1)
    target_level_offset: int = Field(ge=0, le=3)
    """Target level relative to the character, capped at ``max_target_level``."""
    note: str = Field(min_length=1)


class ArmorProficiency(_Frozen):
    type: ArmorType
    from_level: int = Field(default=1, ge=1)


class ClassDef(_Cited):
    name: ClassName
    label: str = Field(min_length=1)
    races: tuple[Race, ...] = Field(min_length=1)
    armor: tuple[ArmorProficiency, ...] = Field(min_length=1)
    weapons: tuple[WeaponType, ...] = Field(min_length=1)
    shields: bool
    dual_wield_from_level: int | None = Field(default=None, ge=1)
    relic: RelicType | None = None
    roles: tuple[str, ...] = Field(min_length=1)

    def armor_from_level(self, armor_type: ArmorType) -> int | None:
        """The level the class can wear ``armor_type`` from, or None if never."""
        return next((p.from_level for p in self.armor if p.type == armor_type), None)


class RaceDef(_Cited):
    name: Race
    label: str = Field(min_length=1)
    faction: Faction
    weapon_skill_bonus: dict[WeaponType, int] = Field(default_factory=dict)


class StatDef(_Frozen):
    stat: Stat
    label: str = Field(min_length=1)
    unit: Literal["points", "percent", "skill", "dps"]
    group: Literal["primary", "defense", "physical", "caster", "regen", "resistance", "weapon"]
    description: str = Field(min_length=1)


class Conversion(_Frozen):
    """How much of the target stat one point of the source stat gives.

    Written as the source states it: ``per_point`` (2 attack power per Strength) or
    ``points_per_unit`` (20 Agility per 1% crit).
    """

    per_point: float | None = Field(default=None, gt=0)
    points_per_unit: float | None = Field(default=None, gt=0)
    note: str | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Conversion:
        if (self.per_point is None) == (self.points_per_unit is None):
            raise ValueError("a conversion gives per_point or points_per_unit, not both")
        return self

    @property
    def rate(self) -> float:
        """Target units per point of the source stat."""
        if self.per_point is not None:
            return self.per_point
        assert self.points_per_unit is not None
        return 1.0 / self.points_per_unit


class ConversionTable(_Cited):
    """Conversions per class, valid at ``level``; at other levels they are approximate."""

    level: int = Field(ge=1)
    by_class: dict[ClassName, dict[str, Conversion]]
    note: str | None = None

    @field_validator("by_class")
    @classmethod
    def _keys_name_two_stats(
        cls, by_class: dict[ClassName, dict[str, Conversion]]
    ) -> dict[ClassName, dict[str, Conversion]]:
        known = {stat.value for stat in Stat}
        for class_name, table in by_class.items():
            for key in table:
                source, arrow, target = key.partition("->")
                if not arrow or source not in known or target not in known:
                    raise ValueError(f"{class_name}: conversion {key!r} is not 'stat->stat'")
        return by_class


class CapDef(_Cited):
    """A named cap: a formula kind from the calculations layer, applied to one stat."""

    kind: CapKind
    stat: Stat
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class MeleeMissParameters(_Cited):
    """Inputs of the melee and ranged miss chance formula, in percent and skill points.

    With ``gap`` = target defense minus attacker weapon skill (each level x
    ``skill_per_level`` plus bonuses): miss = ``base_miss`` + gap x ``per_point_small_gap``
    when the gap is at most ``small_gap_limit``, else ``base_miss`` + gap x
    ``per_point_large_gap``. Beyond the limit, hit from gear is suppressed by
    ``suppression_per_point_beyond_limit`` for each point of gap above it.
    """

    base_miss: float = Field(ge=0)
    small_gap_limit: int = Field(ge=0)
    per_point_small_gap: float = Field(ge=0)
    per_point_large_gap: float = Field(ge=0)
    suppression_per_point_beyond_limit: float = Field(ge=0)
    dual_wield_penalty: float = Field(ge=0)
    """Added to the white-hit miss chance when dual wielding."""
    skill_per_level: int = Field(ge=1)
    """Base weapon skill and defense per level."""


class SpellMissParameters(_Cited):
    """Chance for a spell to hit, by target level minus caster level, in percent."""

    hit_chance_by_level_gap: dict[int, float]
    per_level_beyond_table: float = Field(ge=0)
    """Hit chance lost for each level of gap beyond the largest one in the table."""
    max_hit_chance: float = Field(gt=0, le=100)

    @field_validator("hit_chance_by_level_gap")
    @classmethod
    def _from_zero(cls, table: dict[int, float]) -> dict[int, float]:
        if sorted(table) != list(range(len(table))):
            raise ValueError("the spell hit table must cover level gaps 0, 1, 2, ... in order")
        return table


class DefenseParameters(_Cited):
    """Inputs of the crit-immunity breakpoint.

    An attacker's crit chance against a player is ``base_crit_chance`` plus
    ``crit_change_per_skill_point`` for each point of attacker skill above the defender's
    defense; defense that pushes it to zero makes the defender immune to crits.
    """

    base_crit_chance: float = Field(ge=0)
    crit_change_per_skill_point: float = Field(gt=0)
    skill_per_level: int = Field(ge=1)


class Mechanics(_Frozen):
    melee_miss: MeleeMissParameters
    spell_miss: SpellMissParameters
    defense: DefenseParameters


class Ruleset(_Frozen):
    """One game version, as ``configs/rulesets/<id>.yaml`` describes it."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(pattern=SEMVER)
    label: str = Field(min_length=1)
    game_family: str = Field(min_length=1)
    rules_basis: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    min_level: int = Field(default=1, ge=1)
    max_level: int = Field(ge=1)
    max_target_level: int = Field(ge=1)
    default_phase: int = Field(ge=1)
    phases: tuple[PhaseDef, ...] = Field(min_length=1)
    content_modes: tuple[ContentModeDef, ...] = Field(min_length=1)
    classes: tuple[ClassDef, ...] = Field(min_length=1)
    races: tuple[RaceDef, ...] = Field(min_length=1)
    stats: tuple[StatDef, ...] = Field(min_length=1)
    conversions: ConversionTable
    caps: dict[str, CapDef]
    mechanics: Mechanics
    assumptions: tuple[str, ...] = ()
    sources: tuple[SourceRef, ...] = Field(min_length=1)
    validation_status: ValidationStatus

    @model_validator(mode="after")
    def _consistent(self) -> Ruleset:
        if not self.min_level <= self.max_level <= self.max_target_level:
            raise ValueError("levels must satisfy min_level <= max_level <= max_target_level")
        numbers = [phase.number for phase in self.phases]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("phases must be numbered 1, 2, 3, ... in order")
        if self.default_phase not in numbers:
            raise ValueError(f"default_phase {self.default_phase} is not a phase")
        self._unique("content mode", [mode.mode for mode in self.content_modes])
        self._unique("class", [c.name for c in self.classes])
        self._unique("race", [r.name for r in self.races])
        self._unique("stat", [s.stat for s in self.stats])
        races = {race.name for race in self.races}
        for class_def in self.classes:
            unknown = set(class_def.races) - races
            if unknown:
                raise ValueError(f"{class_def.name}: unknown races {sorted(unknown)}")
        allowed = {stat_def.stat for stat_def in self.stats}
        for class_name, table in self.conversions.by_class.items():
            for key in table:
                source, _, target = key.partition("->")
                if Stat(source) not in allowed or Stat(target) not in allowed:
                    raise ValueError(f"{class_name}: conversion {key} uses a stat not allowed")
        for name, cap in self.caps.items():
            if cap.stat not in allowed:
                raise ValueError(f"cap {name} is on {cap.stat}, which the ruleset does not allow")
        source_ids = [source.id for source in self.sources]
        self._unique("source id", source_ids)
        missing = self._cited() - set(source_ids)
        if missing:
            raise ValueError(f"cited sources not listed under sources: {sorted(missing)}")
        return self

    @staticmethod
    def _unique(what: str, values: Sequence[object]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"each {what} may appear once")

    def _cited(self) -> set[str]:
        blocks: list[_Cited] = [
            *self.phases,
            *self.content_modes,
            *self.classes,
            *self.races,
            self.conversions,
            *self.caps.values(),
            self.mechanics.melee_miss,
            self.mechanics.spell_miss,
            self.mechanics.defense,
        ]
        return {source for block in blocks for source in block.sources}

    def class_def(self, class_name: ClassName) -> ClassDef:
        return next(c for c in self.classes if c.name == class_name)

    def race_def(self, race: Race) -> RaceDef:
        return next(r for r in self.races if r.name == race)

    def content_mode(self, mode: ContentMode) -> ContentModeDef:
        return next(m for m in self.content_modes if m.mode == mode)

    def stat_def(self, stat: Stat) -> StatDef | None:
        return next((s for s in self.stats if s.stat == stat), None)

    def allows(self, stat: Stat) -> bool:
        return any(s.stat == stat for s in self.stats)

    def conversion(self, class_name: ClassName, key: str) -> Conversion | None:
        return self.conversions.by_class.get(class_name, {}).get(key)

    @property
    def content_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
