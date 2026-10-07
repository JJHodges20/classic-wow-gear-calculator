"""CharacterContext: who the item is being evaluated for.

The value of an item changes with these assumptions, so a score is always computed for a
context and records it.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wow_gear.core.hashing import content_hash
from wow_gear.models.enums import (
    WEAPON_DPS_STATS,
    ClassName,
    ContentMode,
    CreatureType,
    Faction,
    Race,
    Role,
    Stat,
    WeaponType,
)


class CharacterContext(BaseModel):
    """The context a score is computed in.

    ``current_stats`` are the totals the character's current gear provides (what the item
    tooltips add up to), not the character sheet: base values and talents come from the
    ruleset and the profile. They make cap-sensitive results exact; without them the
    calculator warns that capped stats may be over- or under-valued.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ruleset: str = Field(min_length=1)
    phase: int = Field(ge=1)
    level: int = Field(ge=1)
    class_name: ClassName
    role: Role
    profile_id: str = Field(min_length=1)
    faction: Faction | None = None
    race: Race | None = None
    content_mode: ContentMode = ContentMode.RAID
    target_level: int | None = Field(default=None, ge=1)
    """Overrides the target level the content mode implies."""
    target_creature_type: CreatureType | None = None
    """Lets conditional stats such as "+AP against Undead" count."""
    main_hand_type: WeaponType | None = None
    """The melee weapon type the character fights with, for weapon-skill bonuses."""
    ranged_type: WeaponType | None = None
    """The ranged weapon type, for a hunter's weapon skill."""
    current_stats: dict[Stat, float] | None = None
    buffs: tuple[str, ...] = ()
    encounter: str | None = None

    @field_validator("current_stats")
    @classmethod
    def _finite_gear_totals(cls, stats: dict[Stat, float] | None) -> dict[Stat, float] | None:
        if stats is None:
            return None
        for stat, value in stats.items():
            if stat in WEAPON_DPS_STATS:
                raise ValueError(f"{stat} is not a gear total")
            if not math.isfinite(value):
                raise ValueError(f"current {stat} must be a finite number")
        return dict(sorted((stat, float(value)) for stat, value in stats.items() if value))

    @property
    def has_current_stats(self) -> bool:
        return self.current_stats is not None

    def current(self, stat: Stat) -> float:
        return (self.current_stats or {}).get(stat, 0.0)

    @property
    def fingerprint(self) -> str:
        return content_hash(self.model_dump(mode="json"))
