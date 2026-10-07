"""Comparing items for one context: rank them, name a recommendation, explain the difference.

Every item is scored from the same baseline - current gear minus the item being replaced - so
the scores are directly comparable. Usable items rank first. The explanation is the
difference between the recommended item's components and those of the item it is measured
against, largest first, so a player can see why the recommendation is what it is and what
would change it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from wow_gear.core.errors import DataValidationError
from wow_gear.core.hashing import content_hash
from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult, ExplanationLine, Outcome, Upgrade
from wow_gear.models.enums import EquipmentSlot
from wow_gear.models.gear import BLOCKS_OFF_HAND, EQUIPMENT_SLOTS
from wow_gear.models.item import Item
from wow_gear.models.labels import SLOT_LABELS
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import ComponentKind, Confidence, ScoreComponent, ScoreResult
from wow_gear.scoring.engine import score_item

TIE_ABSOLUTE = 0.05
"""Score gaps below this (in the profile's unit) are ties."""
TIE_RELATIVE = 0.005
"""Score gaps below this share of the larger score are ties: weights are not that precise."""
WHY_LINES = 4
"""How many component differences the one-line explanation names."""

_EPSILON = 1e-9
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
_HANDS = frozenset({EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND})


def unit_abbreviation(unit: str) -> str:
    """ "attack power equivalents (AP)" -> "AP"; a unit without one is returned whole."""
    match = re.search(r"\(([^()]+)\)\s*$", unit)
    return match.group(1) if match else unit


def is_tie(first: float, second: float) -> bool:
    gap = abs(first - second)
    return gap < TIE_ABSOLUTE or gap < TIE_RELATIVE * max(abs(first), abs(second))


def _rank_key(result: ScoreResult) -> tuple[bool, float, str, str]:
    return (not result.eligible, -result.score, result.item_name, result.item_id)


def _signed(value: float) -> str:
    return "0" if abs(value) < 0.05 else f"{value:+.1f}"


def in_sentence(label: str) -> str:
    """A label inside a sentence: "Crit" -> "crit", but "DPS" stays "DPS"."""
    if len(label) > 1 and label[1].islower():
        return label[0].lower() + label[1:]
    return label


def _join(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _unscored(component: ScoreComponent) -> bool:
    return not component.scored


def _reduction(component: ScoreComponent, item_name: str) -> str | None:
    """Why only part of a component's amount counted, if it did."""
    if abs(component.effective_amount - component.amount) <= _EPSILON:
        return None
    if component.note and component.note.startswith("Not counted:"):
        return f"{item_name}: {component.note[0].lower()}{component.note[1:]}"
    if abs(component.effective_amount) <= _EPSILON:
        return f"{item_name}: none of its {component.amount:g} counts"
    return f"{item_name}: {component.effective_amount:g} of its {component.amount:g} counts"


def explain(
    first: ScoreResult, second: ScoreResult
) -> tuple[tuple[ExplanationLine, ...], tuple[str, ...], tuple[str, ...]]:
    """The component differences between two results, largest first.

    Returns the explanation lines, the labels of stats the profile does not value, and the
    effects neither score counts. A component that is equal on both items is left out
    unless a cap or an exclusive group cut it down on one of them: "0 from hit" is part of
    the answer when the hit was wasted.
    """
    return explain_components(
        first.item_name, first.components, second.item_name, second.components
    )


def explain_components(
    first_name: str,
    first_components: Sequence[ScoreComponent],
    second_name: str,
    second_components: Sequence[ScoreComponent],
) -> tuple[tuple[ExplanationLine, ...], tuple[str, ...], tuple[str, ...]]:
    """``explain`` for any two sets of components - two items, or two whole sets of gear."""
    a_parts = {c.key: c for c in first_components if not _unscored(c)}
    b_parts = {c.key: c for c in second_components if not _unscored(c)}
    lines: list[ExplanationLine] = []
    not_valued: list[str] = []
    for key in dict.fromkeys([*a_parts, *b_parts]):
        a, b = a_parts.get(key), b_parts.get(key)
        sample = a or b
        assert sample is not None
        valued = sample.kind == ComponentKind.THRESHOLD or any(
            part is not None and part.weight != 0 for part in (a, b)
        )
        if not valued:
            not_valued.append(sample.label)
            continue
        first_value = a.contribution if a else 0.0
        second_value = b.contribution if b else 0.0
        delta = first_value - second_value
        reasons = [
            reason
            for part, name in ((a, first_name), (b, second_name))
            if part is not None and sample.kind != ComponentKind.THRESHOLD
            for reason in [_reduction(part, name)]
            if reason
        ]
        if abs(delta) <= _EPSILON and not reasons:
            continue
        note = "; ".join(reasons) or None
        text = f"{_signed(delta)} from {in_sentence(sample.label)}" + (f" ({note})" if note else "")
        lines.append(
            ExplanationLine(
                key=key,
                label=sample.label,
                kind=sample.kind,
                stat=sample.stat,
                first_amount=a.amount if a else 0.0,
                second_amount=b.amount if b else 0.0,
                first_value=first_value,
                second_value=second_value,
                delta=delta,
                note=note,
                text=text,
            )
        )
    lines.sort(key=lambda line: (-abs(line.delta), line.label))
    not_scored = [
        f"{name}: {component.label}"
        for name, components in ((first_name, first_components), (second_name, second_components))
        for component in components
        if _unscored(component)
    ]
    return tuple(lines), tuple(dict.fromkeys(not_valued)), tuple(dict.fromkeys(not_scored))


def footprint_note(items: Sequence[Item], replacing: Item | None = None) -> str | None:
    """A warning when the items (and the equipped one) do not fill the same equipment slot."""
    items = [*items, *([replacing] if replacing is not None else [])]
    two_handed = [item for item in items if item.slot in BLOCKS_OFF_HAND]
    hands = [
        item
        for item in items
        if item.slot not in BLOCKS_OFF_HAND and _HANDS.intersection(EQUIPMENT_SLOTS[item.slot])
    ]
    if two_handed and hands:
        return (
            f"{two_handed[0].name} is a two-handed weapon: it also takes the off hand, so it "
            "should be weighed against a main-hand and off-hand pair, not one weapon. Each "
            "item here is scored alone."
        )
    slots = [set(EQUIPMENT_SLOTS[item.slot]) for item in items]
    if any(not (a & b) for index, a in enumerate(slots) for b in slots[index + 1 :]):
        names = ", ".join(sorted({SLOT_LABELS[item.slot] for item in items}))
        return (
            f"These items are worn in different slots ({names}): each is scored alone, and "
            "the higher score is not a choice between them."
        )
    return None


def _confidence(results: Sequence[ScoreResult]) -> Confidence:
    worst = min(results, key=lambda result: _CONFIDENCE_ORDER[result.confidence.level])
    reasons = tuple(dict.fromkeys(r for result in results for r in result.confidence.reasons))
    return Confidence(level=worst.confidence.level, reasons=reasons)


def compare_items(
    items: Sequence[Item],
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
    *,
    replacing: Item | None = None,
) -> ComparisonResult:
    """Score, rank and explain ``items`` for ``context`` under ``profile``.

    ``replacing`` is the item currently equipped in the slot: every candidate is scored from
    the gear without it, and each one's change against it is reported as an upgrade delta.
    """
    if not items:
        raise DataValidationError("nothing to compare")
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise DataValidationError("an item is listed twice")
    scored = [score_item(item, context, profile, ruleset, replacing=replacing) for item in items]
    ranked = sorted(scored, key=_rank_key)
    usable = [result for result in ranked if result.eligible]
    abbreviation = unit_abbreviation(profile.score_unit)

    outcome: Outcome
    first: ScoreResult | None = None
    second: ScoreResult | None = None
    if len(ranked) == 1:
        outcome, first = "single", ranked[0]
    elif not usable:
        outcome = "none_usable"
    elif len(usable) == 1:
        outcome, first, second = "only_usable", usable[0], ranked[1]
    else:
        first, second = usable[0], usable[1]
        outcome = "tie" if is_tie(first.score, second.score) else "winner"

    delta = first.score - second.score if first and second else 0.0
    lines: tuple[ExplanationLine, ...] = ()
    not_valued: tuple[str, ...] = ()
    not_scored: tuple[str, ...] = ()
    if first is not None and second is not None:
        lines, not_valued, not_scored = explain(first, second)
    elif first is not None:
        not_valued = tuple(
            dict.fromkeys(
                c.label
                for c in first.components
                if not _unscored(c) and c.weight == 0 and c.kind != ComponentKind.THRESHOLD
            )
        )
        not_scored = tuple(
            f"{first.item_name}: {c.label}" for c in first.components if _unscored(c)
        )

    headline = _headline(outcome, first, second, delta, profile.label, abbreviation)
    differences = [line.text for line in lines if abs(line.delta) >= 0.05][:WHY_LINES]
    wasted = [line.text for line in lines if abs(line.delta) < 0.05 and line.note][:1]
    why = _join(differences + wasted)
    winner = first.item_id if first is not None and outcome in ("winner", "only_usable") else None

    tied = {r.item_id for r in (first, second) if r is not None}
    labelled = []
    for rank, result in enumerate(ranked, start=1):
        if not result.eligible:
            label = "Not usable"
        elif outcome == "tie" and result.item_id in tied:
            label = "Effectively tied"
        elif result.item_id == winner:
            label = "Recommended under this profile"
        elif outcome == "single":
            label = "Scored"
        else:
            label = f"{result.score - usable[0].score:+.1f} {abbreviation}"
        labelled.append(result.model_copy(update={"rank": rank, "recommendation_label": label}))

    notes: list[str] = []
    footprint = footprint_note(items, replacing)
    if footprint:
        notes.append(footprint)
    for result in ranked:
        if not result.eligible:
            notes.append(f"{result.item_name} is not usable: {'; '.join(result.ineligibility)}.")
    if not context.has_current_stats and any(
        warning.code == "cap_sensitive_without_current_stats"
        for result in scored
        for warning in result.warnings
    ):
        notes.append(
            "Cap-sensitive stats were scored without your current gear totals, so the ranking "
            "may change once you enter them."
        )

    replaced_result = None
    upgrades: tuple[Upgrade, ...] = ()
    if replacing is not None:
        replaced_result = score_item(replacing, context, profile, ruleset, replacing=replacing)
        upgrades = tuple(
            Upgrade(
                item_id=result.item_id,
                item_name=result.item_name,
                delta=result.score - replaced_result.score,
            )
            for result in labelled
        )

    deciding = [result for result in (first, second) if result is not None] or ranked
    return ComparisonResult(
        profile_id=profile.id,
        profile_version=profile.version,
        profile_label=profile.label,
        ruleset_id=ruleset.id,
        ruleset_version=ruleset.version,
        score_unit=profile.score_unit,
        unit_abbreviation=abbreviation,
        results=tuple(labelled),
        outcome=outcome,
        winner_id=winner,
        first_id=first.item_id if first and second else None,
        second_id=second.item_id if first and second else None,
        score_delta=delta,
        headline=headline,
        why=why,
        lines=lines,
        not_valued=not_valued,
        not_scored=not_scored,
        replaced=replaced_result,
        upgrades=upgrades,
        notes=tuple(notes),
        confidence=_confidence(deciding),
        fingerprint=content_hash(
            {
                "results": [result.context_fingerprint for result in labelled],
                "replacing": replacing.version if replacing is not None else None,
            }
        ),
    )


def _headline(
    outcome: Outcome,
    first: ScoreResult | None,
    second: ScoreResult | None,
    delta: float,
    profile_label: str,
    unit: str,
) -> str:
    if outcome == "none_usable" or first is None:
        return "None of these items is usable by this character."
    if outcome == "single" or second is None:
        return f"{first.item_name} scores {first.score:.1f} {unit} for {profile_label}."
    if outcome == "tie":
        return (
            f"{first.item_name} and {second.item_name} are effectively equal for "
            f"{profile_label} ({first.score:.1f} and {second.score:.1f} {unit})."
        )
    if outcome == "only_usable":
        return (
            f"{first.item_name} is the only usable choice ({first.score:.1f} {unit}); "
            f"{second.item_name} would score {second.score:.1f} {unit}."
        )
    return (
        f"{first.item_name} is better for {profile_label} by {delta:.1f} {unit} "
        f"({first.score:.1f} against {second.score:.1f})."
    )
