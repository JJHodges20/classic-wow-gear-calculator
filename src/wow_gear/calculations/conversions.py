"""Stat conversions: how much of one stat another provides, for a class (ruleset data)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from wow_gear.models.enums import ClassName, Stat
from wow_gear.models.profile import DerivedStatRule
from wow_gear.models.ruleset import Conversion, Ruleset


@dataclass(frozen=True)
class DerivedAmount:
    """``amount`` of ``target`` that ``source_amount`` of ``source`` provides."""

    source: Stat
    target: Stat
    source_amount: float
    rate: float
    amount: float
    conversion: Conversion


def describe(conversion: Conversion, source: str, target: str, percent: bool) -> str:
    """The conversion as its sources state it: "20 Agility per 1% crit", "2 attack power per Strength"."""
    if conversion.points_per_unit is not None:
        unit = "1%" if percent else "1"
        return f"{conversion.points_per_unit:g} {source} per {unit} {target}"
    return f"{conversion.per_point:g} {target} per {source}"


def derive(
    amounts: Mapping[Stat, float],
    rules: Iterable[DerivedStatRule],
    ruleset: Ruleset,
    class_name: ClassName,
) -> list[DerivedAmount]:
    """Apply each rule whose source stat is present in ``amounts``."""
    derived = []
    for rule in rules:
        source_amount = amounts.get(rule.source, 0.0)
        if not source_amount:
            continue
        conversion = ruleset.conversion(class_name, rule.conversion)
        if conversion is None:
            continue
        derived.append(
            DerivedAmount(
                source=rule.source,
                target=rule.target,
                source_amount=source_amount,
                rate=conversion.rate,
                amount=source_amount * conversion.rate,
                conversion=conversion,
            )
        )
    return derived
