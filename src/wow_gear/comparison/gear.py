"""A whole set of gear: what it is worth, what each piece adds, where the caps stand, and how
putting one item on changes the whole character.

The engine scores the whole set (``scoring.gear.evaluate_gear``). A piece is worth what the
character loses without it, and a replacement is worth the change in the whole set's value:
both are differences between two whole sets, so both account for the caps the rest of the
gear already fills - and for a weapon whose type changes the character's weapon skill, and
with it the hit cap.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence

from wow_gear.calculations.caps import cap_label, resolve_cap, uses_weapon_skill
from wow_gear.comparison.compare import (
    TIE_ABSOLUTE,
    explain_components,
    in_sentence,
    unit_abbreviation,
)
from wow_gear.core.errors import DataValidationError
from wow_gear.core.hashing import content_hash
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import WEAPON_SKILL_STATS, EquipmentSlot, Stat
from wow_gear.models.gear import (
    BLOCKS_OFF_HAND,
    EQUIPMENT_SLOTS,
    CapStatus,
    GearAnalysis,
    ReplacementResult,
    SetPieces,
    SlotValue,
    WeakSlot,
)
from wow_gear.models.item import Item
from wow_gear.models.labels import EQUIPMENT_SLOT_LABELS, SLOT_LABELS
from wow_gear.models.profile import BuildProfile, Threshold
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import ComponentKind
from wow_gear.scoring.amounts import amount_text, is_percent, number_text, stat_label
from wow_gear.scoring.engine import ENGINE_VERSION, CapInfo, cap_curves, measured_totals, score_item
from wow_gear.scoring.gear import (
    GearEvaluation,
    combine,
    evaluate_gear,
    item_totals,
    with_totals,
)

WEAK_ITEM_LEVEL_GAP = 10
"""A piece at least this many item levels below the median of the gear is pointed out as one
of the weakest. An assumption: item level is only a rough sign of how much an item gives."""
WEAK_BY_ITEM_LEVEL = 3
"""At most this many pieces are pointed out for their item level."""

_EPSILON = 1e-9
_MIN_ITEM_LEVELS = 4  # with fewer pieces a median says nothing
_SKILL_STATS = frozenset(WEAPON_SKILL_STATS.values())
_SETS_WEAPON_TYPE = frozenset({EquipmentSlot.MAIN_HAND, EquipmentSlot.RANGED})


def check_gear(gear: Mapping[EquipmentSlot, Item]) -> None:
    """Raise ``DataValidationError`` unless ``gear`` could be worn together."""
    for slot, item in gear.items():
        if slot not in EQUIPMENT_SLOTS[item.slot]:
            raise DataValidationError(
                f"{item.name} ({SLOT_LABELS[item.slot].lower()}) cannot be worn in the "
                f"{EQUIPMENT_SLOT_LABELS[slot].lower()} slot"
            )
    main = gear.get(EquipmentSlot.MAIN_HAND)
    if main is not None and main.slot in BLOCKS_OFF_HAND and EquipmentSlot.OFF_HAND in gear:
        raise DataValidationError(f"{main.name} is a two-handed weapon: the off hand must be empty")
    worn = Counter(item.id for item in gear.values() if item.unique)
    for item in gear.values():
        if worn[item.id] > 1:
            raise DataValidationError(f"{item.name} is unique: it can be worn only once")


def set_label(names: Sequence[str]) -> str | None:
    """A name for a set, read from two or more of its pieces: "Helm of Wrath" and "Pauldrons
    of Wrath" -> "Wrath"; "Devilsaur Gauntlets" and "Devilsaur Leggings" -> "Devilsaur".
    None when the names share nothing."""
    if len(names) < 2:
        return None
    if all(" of " in name for name in names):
        tails = {name.rsplit(" of ", 1)[1] for name in names}
        if len(tails) == 1:
            return tails.pop()
    prefix: list[str] = []
    for column in zip(*(name.split() for name in names), strict=False):
        if len(set(column)) != 1:
            break
        prefix.append(column[0])
    return " ".join(prefix) or None


def set_pieces(items: Sequence[Item]) -> tuple[SetPieces, ...]:
    """The sets ``items`` include two or more pieces of - the ones a bonus can apply to -
    most pieces first. The data names no sets, so each is named from its pieces."""
    groups: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.set_id is not None:
            groups[item.set_id].append(item)
    ordered = sorted(groups.items(), key=lambda entry: -len(entry[1]))
    return tuple(
        SetPieces(
            set_id=set_id,
            label=pieces[0].set_name
            or set_label([piece.name for piece in pieces])
            or f"Set {set_id}",
            items=tuple(piece.name for piece in pieces),
        )
        for set_id, pieces in ordered
        if len(pieces) > 1
    )


def _cap(
    stat: Stat,
    info: CapInfo,
    total: float,
    profile: BuildProfile,
    ruleset: Ruleset,
    unit: str,
) -> CapStatus:
    name = stat_label(stat, ruleset)
    hard = next((cap for cap in profile.hard_caps if cap.stat == stat), None)
    soft = next((cap for cap in profile.soft_caps if cap.stat == stat), None)
    reference = soft.starts_at if soft is not None else hard.cap if hard is not None else None
    assert reference is not None  # cap_curves only holds the profile's caps
    label = cap_label(reference, name, ruleset)
    if soft is not None and soft.ends_at is not None:
        end_label = cap_label(soft.ends_at, name, ruleset)
    else:
        end_label = cap_label(hard.cap, name, ruleset) if hard is not None else label
    curve = info.curve

    def amount(value: float) -> str:
        return amount_text(stat, value, ruleset)

    had = f"{name} {amount(total)} from gear"
    worth: float | None = None
    if total < curve.full_until - _EPSILON:
        gap = curve.full_until - total
        worth = profile.weight_of(stat) * curve.counted(total, gap)
        state = "short"
        message = (
            f"{had}: {amount(gap)} short of the {in_sentence(label)} "
            f"({amount(curve.full_until)}); reaching it is worth {worth:.1f} {unit}."
        )
        if total < curve.dead_zone - _EPSILON:
            message += f" The first {amount(curve.dead_zone)} counts for nothing on this target."
    elif info.kind == "soft" and total < curve.soft_until - _EPSILON:
        state = "reached"
        until = "" if math.isinf(curve.soft_until) else f" up to {amount(curve.soft_until)}"
        message = (
            f"{had}: past the {in_sentence(label)} ({amount(curve.full_until)}); more counts "
            f"at {curve.soft_multiplier:.0%} of its value{until}."
        )
    elif info.kind == "hard" and total <= curve.full_until + _EPSILON:
        state = "reached"
        message = f"{had}: exactly at the {in_sentence(label)}."
    else:
        limit = curve.soft_until if info.kind == "soft" else curve.full_until
        state = "over"
        message = (
            f"{had}: {amount(total - limit)} past the {in_sentence(end_label)} "
            f"({amount(limit)}) counts for nothing."
        )
    return CapStatus(
        stat=stat,
        label=label,
        kind="soft cap" if info.kind == "soft" else "hard cap",
        target=curve.full_until,
        total=total,
        percent=is_percent(stat, ruleset),
        state=state,
        worth=worth,
        message=message,
        derivation=info.derivation,
    )


def _breakpoint(
    rule: Threshold,
    total: float,
    curves: Mapping[Stat, CapInfo],
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
    unit: str,
) -> CapStatus:
    evaluated = resolve_cap(rule.at, ruleset, context)
    target = evaluated.cap
    name = stat_label(rule.stat, ruleset)
    had = f"{name} {amount_text(rule.stat, total, ruleset)} from gear"
    worth: float | None = None
    if total < target - _EPSILON:
        gap = target - total
        info = curves.get(rule.stat)
        counted = info.curve.counted(total, gap) if info is not None else gap
        worth = rule.bonus + profile.weight_of(rule.stat) * counted
        state = "short"
        message = (
            f"{rule.label}: {had}, {amount_text(rule.stat, gap, ruleset)} short of "
            f"{amount_text(rule.stat, target, ruleset)}; reaching it is worth {worth:.1f} {unit}."
        )
    else:
        state = "reached"
        message = (
            f"{rule.label}: reached ({had}; {amount_text(rule.stat, target, ruleset)} needed)."
        )
    return CapStatus(
        stat=rule.stat,
        label=rule.label,
        kind="breakpoint",
        target=target,
        total=total,
        percent=is_percent(rule.stat, ruleset),
        state=state,
        worth=worth,
        message=message,
        derivation=evaluated.derivation,
    )


def cap_status(
    evaluation: GearEvaluation, profile: BuildProfile, ruleset: Ruleset
) -> tuple[CapStatus, ...]:
    """Where each of the profile's caps and breakpoints stands for the evaluated gear."""
    context = evaluation.context
    measured = measured_totals(evaluation.totals, context, profile, ruleset)
    curves = cap_curves(profile, ruleset, context)
    unit = unit_abbreviation(profile.score_unit)
    statuses = [
        _cap(stat, info, measured.get(stat, 0.0), profile, ruleset, unit)
        for stat, info in curves.items()
    ]
    statuses.extend(
        _breakpoint(rule, measured.get(rule.stat, 0.0), curves, context, profile, ruleset, unit)
        for rule in profile.thresholds
    )
    return tuple(statuses)


def _not_valued(
    totals: Mapping[Stat, float], profile: BuildProfile, ruleset: Ruleset
) -> tuple[str, ...]:
    """The gear's stats that the profile gives no value, directly or through a conversion."""
    targets = {weight.stat for weight in profile.stat_weights if weight.weight}
    targets |= {rule.stat for rule in profile.thresholds}
    valued = targets | {rule.source for rule in profile.derived_stats if rule.target in targets}
    if uses_weapon_skill(profile, ruleset):
        valued |= _SKILL_STATS  # weapon skill moves the hit cap
    return tuple(
        f"{stat_label(stat, ruleset)} {amount_text(stat, value, ruleset)}"
        for stat, value in totals.items()
        if stat not in valued and value > 0
    )


def _without(gear: Mapping[EquipmentSlot, Item], slot: EquipmentSlot) -> dict[EquipmentSlot, Item]:
    return {other: item for other, item in gear.items() if other != slot}


def _slot_worth(
    slot: EquipmentSlot,
    item: Item,
    gear: Mapping[EquipmentSlot, Item],
    evaluation: GearEvaluation,
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
) -> float:
    """What the character loses without ``item``: the gear's value less the gear's without it."""
    own = item_totals(item, evaluation.context, profile, ruleset)
    if slot in _SETS_WEAPON_TYPE or _SKILL_STATS.intersection(own):
        # Without it the weapon skill changes, and the hit caps with it: score both sets.
        rest = evaluate_gear(_without(gear, slot), context, profile, ruleset)
        return evaluation.score - rest.score
    # The caps stay where they are, so the difference is the item on top of the rest.
    rest_totals = combine(evaluation.totals, own, sign=-1.0)
    return score_item(item, with_totals(evaluation.context, rest_totals), profile, ruleset).score


def _weakest(slots: Sequence[SlotValue], evaluation: GearEvaluation) -> tuple[WeakSlot, ...]:
    found: list[WeakSlot] = []
    for value in slots:
        if not value.eligible or value.score > TIE_ABSOLUTE:
            continue
        components = evaluation.results[value.slot].components
        if any(component.kind == ComponentKind.PROC for component in components):
            reason = (
                "adds nothing the calculator scores: its proc or on-use effect is not valued "
                "in version 1"
            )
        else:
            reason = "adds nothing under this profile"
        found.append(WeakSlot(slot=value.slot, item_name=value.item_name, reason=reason))
    levels = [value.item_level for value in slots if value.item_level is not None]
    if len(levels) < _MIN_ITEM_LEVELS:
        return tuple(found)
    median = statistics.median(levels)
    flagged = {weak.slot for weak in found}
    low = sorted(
        (
            value
            for value in slots
            if value.item_level is not None
            and value.slot not in flagged
            and median - value.item_level >= WEAK_ITEM_LEVEL_GAP
        ),
        key=lambda value: value.item_level or 0,
    )
    for value in low[:WEAK_BY_ITEM_LEVEL]:
        level = value.item_level or 0
        found.append(
            WeakSlot(
                slot=value.slot,
                item_name=value.item_name,
                reason=(
                    f"item level {level}, {number_text(median - level)} below the median of "
                    f"this gear ({number_text(median)})"
                ),
            )
        )
    return tuple(found)


def _empty(gear: Mapping[EquipmentSlot, Item]) -> tuple[EquipmentSlot, ...]:
    main = gear.get(EquipmentSlot.MAIN_HAND)
    two_handed = main is not None and main.slot in BLOCKS_OFF_HAND
    return tuple(
        slot
        for slot in EquipmentSlot
        if slot not in gear and not (slot == EquipmentSlot.OFF_HAND and two_handed)
    )


def analyse_gear(
    gear: Mapping[EquipmentSlot, Item],
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
) -> GearAnalysis:
    """What ``gear`` is worth to the character of ``context`` under ``profile``, piece by piece."""
    check_gear(gear)
    evaluation = evaluate_gear(gear, context, profile, ruleset)
    unit = unit_abbreviation(profile.score_unit)
    slots = tuple(
        SlotValue(
            slot=slot,
            item_id=item.id,
            item_name=item.name,
            item_level=item.item_level,
            score=_slot_worth(slot, item, gear, evaluation, context, profile, ruleset),
            eligible=evaluation.results[slot].eligible,
            reasons=evaluation.results[slot].ineligibility,
        )
        for slot in EquipmentSlot
        if (item := gear.get(slot)) is not None
    )
    empty = _empty(gear)
    caps = cap_status(evaluation, profile, ruleset)
    sets = set_pieces([gear[slot] for slot in EquipmentSlot if slot in gear])
    notes = []
    if empty:
        notes.append("Empty: " + ", ".join(EQUIPMENT_SLOT_LABELS[slot] for slot in empty) + ".")
    for value in slots:
        if not value.eligible:
            notes.append(f"{value.item_name} is not usable: {'; '.join(value.reasons)}.")
    if sets:
        worn = ", ".join(f"{pieces.label} ({len(pieces.items)} pieces)" for pieces in sets)
        notes.append(f"Set bonuses are not scored in version 1: {worn}.")
    not_scored = tuple(
        dict.fromkeys(
            f"{result.item_name}: {component.label}"
            for result in evaluation.results.values()
            for component in result.components
            if not component.scored and component.kind != ComponentKind.SET_BONUS
        )
    )
    return GearAnalysis(
        profile_id=profile.id,
        profile_version=profile.version,
        ruleset_id=ruleset.id,
        ruleset_version=ruleset.version,
        score_unit=profile.score_unit,
        unit_abbreviation=unit,
        score=evaluation.score,
        components=evaluation.components,
        totals=evaluation.totals,
        slots=slots,
        empty=empty,
        caps=caps,
        under_served=tuple(status.message for status in caps if status.state == "short"),
        not_valued=_not_valued(evaluation.totals, profile, ruleset),
        not_scored=not_scored,
        weakest=_weakest(slots, evaluation),
        sets=sets,
        notes=tuple(notes),
        fingerprint=content_hash(
            {
                "gear": {slot.value: item.version for slot, item in sorted(gear.items())},
                "context": evaluation.context.fingerprint,
                "profile": profile.content_hash,
                "ruleset": ruleset.content_hash,
                "engine": ENGINE_VERSION,
            }
        ),
    )


def displaced(
    gear: Mapping[EquipmentSlot, Item], slot: EquipmentSlot, candidate: Item
) -> tuple[EquipmentSlot, ...]:
    """The slots whose items come off when ``candidate`` goes into ``slot``."""
    if slot not in EQUIPMENT_SLOTS[candidate.slot]:
        raise DataValidationError(
            f"{candidate.name} ({SLOT_LABELS[candidate.slot].lower()}) cannot be worn in the "
            f"{EQUIPMENT_SLOT_LABELS[slot].lower()} slot"
        )
    removed = [slot] if slot in gear else []
    if candidate.slot in BLOCKS_OFF_HAND and EquipmentSlot.OFF_HAND in gear:
        removed.append(EquipmentSlot.OFF_HAND)
    main = gear.get(EquipmentSlot.MAIN_HAND)
    if slot == EquipmentSlot.OFF_HAND and main is not None and main.slot in BLOCKS_OFF_HAND:
        removed.append(EquipmentSlot.MAIN_HAND)
    return tuple(removed)


def _replacement_notes(
    gear: Mapping[EquipmentSlot, Item],
    slot: EquipmentSlot,
    candidate: Item,
    removed: Sequence[EquipmentSlot],
    caps_before: Sequence[CapStatus],
    caps_after: Sequence[CapStatus],
    ruleset: Ruleset,
) -> list[str]:
    notes = []
    if candidate.slot in BLOCKS_OFF_HAND and EquipmentSlot.OFF_HAND in removed:
        pair = " and ".join(gear[other].name for other in removed)
        notes.append(f"{candidate.name} is a two-handed weapon: it replaces {pair}.")
    elif slot == EquipmentSlot.OFF_HAND and EquipmentSlot.MAIN_HAND in removed:
        two_hander = gear[EquipmentSlot.MAIN_HAND].name
        notes.append(
            f"{candidate.name} takes the off hand, so {two_hander} (two-handed) comes off and "
            "the main hand is left empty."
        )
    if not removed:
        notes.append(f"The {EQUIPMENT_SLOT_LABELS[slot].lower()} slot is empty: nothing comes off.")
    before = {(status.stat, status.label): status for status in caps_before}
    for status in caps_after:
        old = before.get((status.stat, status.label))
        if old is not None and abs(old.target - status.target) > _EPSILON:
            notes.append(
                f"With {candidate.name} the {in_sentence(status.label)} is "
                f"{amount_text(status.stat, status.target, ruleset)} instead of "
                f"{amount_text(status.stat, old.target, ruleset)}: weapon skill moves it. "
                "Version 1 does not value weapon skill itself, only this change in what hit "
                "is worth."
            )
    return notes


def replacement(
    gear: Mapping[EquipmentSlot, Item],
    slot: EquipmentSlot,
    candidate: Item,
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
) -> ReplacementResult:
    """How putting ``candidate`` into ``slot`` changes the whole character."""
    check_gear(gear)
    removed = displaced(gear, slot, candidate)
    changed = {other: item for other, item in gear.items() if other not in removed}
    changed[slot] = candidate
    check_gear(changed)
    before = evaluate_gear(gear, context, profile, ruleset)
    after = evaluate_gear(changed, context, profile, ruleset)
    caps_before = cap_status(before, profile, ruleset)
    caps_after = cap_status(after, profile, ruleset)
    lines, _, _ = explain_components(
        f"With {candidate.name}", after.components, "Current gear", before.components
    )
    notes = _replacement_notes(gear, slot, candidate, removed, caps_before, caps_after, ruleset)
    result = after.results[slot]
    if not result.eligible:
        notes.append(f"{candidate.name} is not usable: {'; '.join(result.ineligibility)}.")
    return ReplacementResult(
        slot=slot,
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        removed=tuple(gear[other].name for other in removed),
        delta=after.score - before.score,
        unit_abbreviation=unit_abbreviation(profile.score_unit),
        score_before=before.score,
        score_after=after.score,
        before=before.totals,
        after=after.totals,
        caps_before=caps_before,
        caps_after=caps_after,
        lines=lines,
        eligible=result.eligible,
        reasons=result.ineligibility,
        notes=tuple(notes),
    )
