"""How numbers and stat amounts are written for people - in one place, for every layer that
shows them: "2,311", "82.82", "7%", "+6.6". Formatting only; no value is changed."""

from __future__ import annotations

from wow_gear.models.enums import Stat
from wow_gear.models.ruleset import Ruleset


def stat_label(stat: Stat, ruleset: Ruleset) -> str:
    """The stat's name as the ruleset gives it: "Attack power", "Spell hit"."""
    stat_def = ruleset.stat_def(stat)
    return stat_def.label if stat_def else stat.value.replace("_", " ").capitalize()


def is_percent(stat: Stat | None, ruleset: Ruleset) -> bool:
    """Whether the stat is counted in percent (hit, crit, dodge)."""
    stat_def = ruleset.stat_def(stat) if stat is not None else None
    return stat_def is not None and stat_def.unit == "percent"


def number_text(value: float) -> str:
    """A number as a player reads it: 3,512, 6, 1.5 - at most two decimals."""
    rounded = round(value, 2)
    if rounded == int(rounded):
        return f"{int(rounded):,}"
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def amount_text(stat: Stat | None, value: float, ruleset: Ruleset) -> str:
    """An amount in its stat's unit: "6%" for hit, "120" for Stamina."""
    return number_text(value) + ("%" if is_percent(stat, ruleset) else "")


def signed_text(value: float, digits: int = 1) -> str:
    """A difference with its sign: "+6.6", "-3.8"; one too small to show is "0.0", never
    "-0.0"."""
    if abs(value) < 0.5 * 10**-digits:
        return f"{0:.{digits}f}"
    return f"{value:+.{digits}f}"
