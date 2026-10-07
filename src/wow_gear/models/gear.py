"""Gear: the items a character wears, a saved character, and what the gear adds up to.

``GearSet`` maps equipment slots to item ids; ``SavedCharacter`` is a named character the
player keeps; ``GearAnalysis`` and ``ReplacementResult`` are what the calculator says about
a whole set of gear and about changing one piece of it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wow_gear.models.comparison import ExplanationLine
from wow_gear.models.enums import ClassName, ContentMode, EquipmentSlot, ItemSlot, Race, Stat
from wow_gear.models.score import ScoreComponent

EQUIPMENT_SLOTS: dict[ItemSlot, tuple[EquipmentSlot, ...]] = {
    ItemSlot.HEAD: (EquipmentSlot.HEAD,),
    ItemSlot.NECK: (EquipmentSlot.NECK,),
    ItemSlot.SHOULDER: (EquipmentSlot.SHOULDER,),
    ItemSlot.BACK: (EquipmentSlot.BACK,),
    ItemSlot.CHEST: (EquipmentSlot.CHEST,),
    ItemSlot.WRIST: (EquipmentSlot.WRIST,),
    ItemSlot.HANDS: (EquipmentSlot.HANDS,),
    ItemSlot.WAIST: (EquipmentSlot.WAIST,),
    ItemSlot.LEGS: (EquipmentSlot.LEGS,),
    ItemSlot.FEET: (EquipmentSlot.FEET,),
    ItemSlot.FINGER: (EquipmentSlot.FINGER_1, EquipmentSlot.FINGER_2),
    ItemSlot.TRINKET: (EquipmentSlot.TRINKET_1, EquipmentSlot.TRINKET_2),
    ItemSlot.ONE_HAND: (EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND),
    ItemSlot.MAIN_HAND: (EquipmentSlot.MAIN_HAND,),
    ItemSlot.OFF_HAND: (EquipmentSlot.OFF_HAND,),
    ItemSlot.HELD_IN_OFF_HAND: (EquipmentSlot.OFF_HAND,),
    ItemSlot.SHIELD: (EquipmentSlot.OFF_HAND,),
    ItemSlot.TWO_HAND: (EquipmentSlot.MAIN_HAND,),
    ItemSlot.RANGED: (EquipmentSlot.RANGED,),
    ItemSlot.RELIC: (EquipmentSlot.RANGED,),
}
"""Where an item of each slot type can be equipped. A two-handed weapon is equipped in the
main hand and also leaves the off hand empty (``BLOCKS_OFF_HAND``)."""

BLOCKS_OFF_HAND = frozenset({ItemSlot.TWO_HAND})


class GearSet(BaseModel):
    """Item ids by equipment slot. Empty slots are simply absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(default="Current gear", min_length=1, max_length=80)
    items: dict[EquipmentSlot, str] = Field(default_factory=dict)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SavedCharacter(_Frozen):
    """A named character: who it is, the build profile it is scored with, and its gear."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=60)
    ruleset: str = Field(min_length=1)
    class_name: ClassName
    race: Race | None = None
    level: int = Field(ge=1)
    phase: int = Field(ge=1)
    profile_id: str = Field(min_length=1)
    content_mode: ContentMode = ContentMode.RAID
    gear: GearSet = Field(default_factory=GearSet)
    notes: str | None = Field(default=None, max_length=500)
    version: int = Field(default=1, ge=1)
    """Goes up with every save."""
    saved_at: datetime | None = None


CapState = Literal["short", "reached", "over"]
CapKind = Literal["hard cap", "soft cap", "breakpoint"]


class SlotValue(_Frozen):
    """An equipped item and what it is worth to the character."""

    slot: EquipmentSlot
    item_id: str
    item_name: str
    item_level: int | None = None
    score: float
    """What the character loses without it: the gear's value less the value of the gear
    without this item, in the profile's unit."""
    eligible: bool = True
    reasons: tuple[str, ...] = ()


class CapStatus(_Frozen):
    """Where the gear's total of a capped stat stands against its cap or breakpoint."""

    stat: Stat
    label: str
    """The cap's name: "Melee hit cap", "Crit immunity"."""
    kind: CapKind
    target: float
    """Where full value ends (a soft cap's start) or the breakpoint is reached."""
    total: float
    """The gear's total as caps measure it, conversions included."""
    percent: bool = False
    state: CapState
    worth: float | None = None
    """For a cap not yet reached: what reaching it adds, in the profile's unit."""
    message: str
    derivation: str = ""
    """How the cap was worked out for this character (target level, weapon skill, talents)."""


class WeakSlot(_Frozen):
    """A piece pointed out as one of the weakest, and why."""

    slot: EquipmentSlot
    item_name: str
    reason: str


class SetPieces(_Frozen):
    """Items of one set the character wears (set bonuses are not scored in version 1)."""

    set_id: str
    label: str
    items: tuple[str, ...]


class GearAnalysis(_Frozen):
    """What a whole set of gear adds up to under a profile, piece by piece."""

    profile_id: str
    profile_version: str
    ruleset_id: str
    ruleset_version: str
    score_unit: str
    unit_abbreviation: str
    score: float
    """The whole gear's value under the profile, from no gear at all."""
    components: tuple[ScoreComponent, ...]
    """Where that value comes from: every item's components added up, largest first."""
    totals: dict[Stat, float]
    """What the gear adds up to, as the current gear totals of a calculation."""
    slots: tuple[SlotValue, ...]
    empty: tuple[EquipmentSlot, ...]
    caps: tuple[CapStatus, ...]
    under_served: tuple[str, ...]
    """Caps and breakpoints the gear falls short of, with what reaching them is worth."""
    not_valued: tuple[str, ...]
    """Stats the gear gives that the profile does not value ("Stamina 120")."""
    not_scored: tuple[str, ...]
    """Effects no score counts: procs, on-use effects, set bonuses, unmet conditions."""
    weakest: tuple[WeakSlot, ...]
    sets: tuple[SetPieces, ...]
    notes: tuple[str, ...] = ()
    fingerprint: str
    """A hash of everything the analysis depends on: the same inputs give the same hash."""


class ReplacementResult(_Frozen):
    """How putting one item on changes the whole character."""

    slot: EquipmentSlot
    candidate_id: str
    candidate_name: str
    removed: tuple[str, ...]
    """Names of the items it takes off (two for a two-hander replacing a pair)."""
    delta: float
    """The change in the whole gear's value under the profile."""
    unit_abbreviation: str
    score_before: float
    score_after: float
    before: dict[Stat, float]
    after: dict[Stat, float]
    caps_before: tuple[CapStatus, ...]
    caps_after: tuple[CapStatus, ...]
    lines: tuple[ExplanationLine, ...] = ()
    """The gear with the candidate against the gear as it is, component by component; the
    deltas add up to ``delta``."""
    eligible: bool = True
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
