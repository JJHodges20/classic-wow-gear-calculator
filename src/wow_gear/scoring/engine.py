"""The scoring engine: one item, one context, one profile, one ruleset -> an explainable score.

The score is the sum of its components and nothing else:

    stat and conversion components   amount that counts after caps x profile weight
    context components               conditional stats whose condition holds
    weapon components                weapon damage per second x its weight
    threshold components             the bonus for reaching a breakpoint
    proc and set-bonus components    listed with zero value: version 1 does not value them

Caps are evaluated against what the character already has: the current gear totals in the
context, minus the item being replaced. Without current gear the baseline is zero and the
result says so.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from wow_gear import __version__ as package_version
from wow_gear.calculations.caps import resolve_cap
from wow_gear.calculations.conversions import DerivedAmount, derive, describe
from wow_gear.calculations.curves import FLAT, ValueCurve
from wow_gear.calculations.levels import target_level
from wow_gear.core.errors import DataValidationError
from wow_gear.core.hashing import content_hash
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import Stat, ValidationStatus
from wow_gear.models.formatting import stat_label
from wow_gear.models.item import Item
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import (
    CapEvent,
    ComponentKind,
    Confidence,
    ScoreComponent,
    ScoreResult,
    ScoreWarning,
    ThresholdEvent,
)
from wow_gear.rulesets.eligibility import eligibility
from wow_gear.scoring.amounts import AmountPart, ItemAmounts, item_amounts

ENGINE_VERSION = "1.0.0"
"""Bump whenever the scoring math changes: stored results name the version they used."""

_EPSILON = 1e-9


@dataclass(frozen=True)
class _Part:
    stat: Stat
    amount: float
    kind: ComponentKind
    label: str
    key: str
    source_stat: Stat | None = None
    note: str | None = None


@dataclass(frozen=True)
class CapInfo:
    """A profile's cap on one stat, evaluated for a context, as the curve the engine counts on."""

    kind: Literal["hard", "soft"]
    curve: ValueCurve
    cap: float
    derivation: str


def cap_curves(
    profile: BuildProfile, ruleset: Ruleset, context: CharacterContext
) -> dict[Stat, CapInfo]:
    """The value curve of every capped stat of ``profile`` in ``context``."""
    caps: dict[Stat, CapInfo] = {}
    for hard in profile.hard_caps:
        evaluated = resolve_cap(hard.cap, ruleset, context)
        caps[hard.stat] = CapInfo(
            kind="hard",
            curve=ValueCurve(dead_zone=evaluated.dead_zone, full_until=evaluated.cap),
            cap=evaluated.cap,
            derivation=evaluated.derivation,
        )
    for soft in profile.soft_caps:
        start = resolve_cap(soft.starts_at, ruleset, context)
        derivation = start.derivation
        if soft.ends_at is not None:
            end = resolve_cap(soft.ends_at, ruleset, context)
            soft_until = max(end.cap, start.cap)
            derivation += f"; reduced value ends at {soft_until:g} ({end.derivation})"
        elif soft.stat in caps:
            soft_until = max(caps[soft.stat].cap, start.cap)
        else:
            soft_until = math.inf
        caps[soft.stat] = CapInfo(
            kind="soft",
            curve=ValueCurve(
                dead_zone=min(start.dead_zone, start.cap),
                full_until=start.cap,
                soft_multiplier=soft.multiplier,
                soft_until=soft_until,
            ),
            cap=start.cap,
            derivation=derivation,
        )
    return caps


def _baseline(
    context: CharacterContext,
    replacing: Item | None,
    profile: BuildProfile,
    ruleset: Ruleset,
) -> dict[Stat, float]:
    baseline = dict(context.current_stats or {})
    if replacing is not None:
        for stat, value in item_amounts(replacing, context, profile, ruleset).totals().items():
            baseline[stat] = baseline.get(stat, 0.0) - value
    return baseline


def _with_derived(totals: dict[Stat, float], derived: list[DerivedAmount]) -> dict[Stat, float]:
    combined = dict(totals)
    for amount in derived:
        combined[amount.target] = combined.get(amount.target, 0.0) + amount.amount
    return combined


def measured_totals(
    totals: Mapping[Stat, float], context: CharacterContext, profile: BuildProfile, ruleset: Ruleset
) -> dict[Stat, float]:
    """Gear totals as caps and breakpoints measure them: with what the profile's conversions
    add (Agility into crit, for example) on top of each stat itself."""
    base = dict(totals)
    return _with_derived(base, derive(base, profile.derived_stats, ruleset, context.class_name))


def _cap_message(stat_name: str, info: CapInfo, before: float, amount: float) -> str:
    pieces = info.curve.segments(before, amount)
    parts = []
    if abs(pieces.dead) > _EPSILON:
        parts.append(f"{abs(pieces.dead):g} falls below {info.curve.dead_zone:g} and is suppressed")
    if abs(pieces.soft) > _EPSILON:
        parts.append(
            f"{abs(pieces.soft):g} is past {info.curve.full_until:g} and counts at "
            f"{info.curve.soft_multiplier:.0%}"
        )
    if abs(pieces.beyond) > _EPSILON:
        end = info.curve.soft_until if info.curve.soft_multiplier else info.curve.full_until
        parts.append(f"{abs(pieces.beyond):g} is beyond the cap of {end:g} and is wasted")
    return f"{stat_name}: " + "; ".join(parts) + f" (from {before:g} in current gear)."


def _confidence(profile: BuildProfile, issues: list[str]) -> Confidence:
    reasons = list(issues)
    if profile.validation_status != ValidationStatus.VALIDATED:
        reasons.insert(0, f"The {profile.label} profile is {profile.validation_status}")
    if not reasons:
        return Confidence(level="high")
    level = "medium" if len(reasons) == 1 else "low"
    return Confidence(level=level, reasons=tuple(reasons))


def _check(item: Item, context: CharacterContext, profile: BuildProfile, ruleset: Ruleset) -> None:
    if not (item.ruleset == context.ruleset == profile.ruleset == ruleset.id):
        raise DataValidationError(
            f"ruleset mismatch: item {item.ruleset}, context {context.ruleset}, "
            f"profile {profile.ruleset}, ruleset {ruleset.id}"
        )
    if context.profile_id != profile.id:
        raise DataValidationError(
            f"the context names profile {context.profile_id}, not {profile.id}"
        )
    if context.class_name != profile.class_name or context.role != profile.role:
        raise DataValidationError(
            f"the {profile.id} profile is for a {profile.class_name} {profile.role}, "
            f"not a {context.class_name} {context.role}"
        )
    if not ruleset.min_level <= context.level <= ruleset.max_level:
        raise DataValidationError(f"level {context.level} is outside {ruleset.label}")


def score_item(
    item: Item,
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
    *,
    replacing: Item | None = None,
) -> ScoreResult:
    """Score ``item`` for ``context`` under ``profile``; ``replacing`` is the item it would replace."""
    _check(item, context, profile, ruleset)
    usable = eligibility(item, context, ruleset)
    amounts = item_amounts(item, context, profile, ruleset)
    baseline = _baseline(context, replacing, profile, ruleset)
    caps = cap_curves(profile, ruleset, context)

    item_totals = amounts.totals()
    derived_item = derive(item_totals, profile.derived_stats, ruleset, context.class_name)
    before_totals = measured_totals(baseline, context, profile, ruleset)
    converted = {amount.source for amount in derived_item}

    pools: dict[Stat, list[_Part]] = defaultdict(list)
    for amount_part in amounts.parts:
        pools[amount_part.stat].append(_from_amount(amount_part))
    for amount in derived_item:
        source_name = stat_label(amount.source, ruleset)
        target_name = stat_label(amount.target, ruleset)
        target_def = ruleset.stat_def(amount.target)
        rate = describe(
            amount.conversion,
            source_name,
            target_name.lower(),
            percent=target_def is not None and target_def.unit == "percent",
        )
        pools[amount.target].append(
            _Part(
                stat=amount.target,
                amount=amount.amount,
                kind=ComponentKind.DERIVED,
                label=f"{source_name} into {target_name.lower()}",
                key=f"derived:{amount.source}->{amount.target}",
                source_stat=amount.source,
                note=f"{amount.source_amount:g} {source_name} at {rate}",
            )
        )

    components: list[ScoreComponent] = []
    cap_events: list[CapEvent] = []
    for stat, parts in pools.items():
        weight = profile.weight_of(stat)
        total = sum(part.amount for part in parts)
        info = caps.get(stat)
        before = before_totals.get(stat, 0.0)
        counted = info.curve.counted(before, total) if info else FLAT.counted(before, total)
        share = counted / total if abs(total) > _EPSILON else 0.0
        for part in parts:
            if weight == 0 and part.kind != ComponentKind.DERIVED and stat in converted:
                continue  # its value is carried by the conversion components
            effective = part.amount * share
            note = part.note
            if weight == 0 and part.kind != ComponentKind.DERIVED:
                note = "Not valued by this profile" + (f". {note}" if note else "")
            components.append(
                ScoreComponent(
                    key=part.key,
                    label=part.label,
                    kind=part.kind,
                    stat=stat,
                    source_stat=part.source_stat,
                    amount=part.amount,
                    effective_amount=effective,
                    weight=weight,
                    contribution=effective * weight,
                    note=note,
                )
            )
        if info is not None and abs(counted - total) > _EPSILON:
            pieces = info.curve.segments(before, total)
            cap_events.append(
                CapEvent(
                    stat=stat,
                    cap_kind=info.kind,
                    cap=info.cap,
                    before=before,
                    after=before + total,
                    item_amount=total,
                    counted_amount=counted,
                    wasted_amount=pieces.dead
                    + pieces.beyond
                    + pieces.soft * (1 - info.curve.soft_multiplier),
                    message=_cap_message(stat_label(stat, ruleset), info, before, total)
                    + f" Cap: {info.derivation}.",
                )
            )

    threshold_events = _thresholds(profile, ruleset, context, pools, before_totals, components)
    components = _apply_exclusions(profile, components)

    for index, effect in enumerate(amounts.unscored):
        components.append(
            ScoreComponent(
                key=f"effect:{index}",
                label=effect.description,
                kind=ComponentKind.PROC,
                amount=0.0,
                effective_amount=0.0,
                weight=0.0,
                contribution=0.0,
                note="Not scored: version 1 does not value procs or on-use effects",
            )
        )
    for index, inactive in enumerate(amounts.inactive):
        effect_stat = inactive.effect.stat
        components.append(
            ScoreComponent(
                key=f"inactive:{index}",
                label=inactive.effect.description,
                kind=ComponentKind.CONTEXT,
                stat=effect_stat,
                amount=inactive.effect.value or 0.0,
                effective_amount=0.0,
                weight=profile.weight_of(effect_stat) if effect_stat else 0.0,
                contribution=0.0,
                note=f"Not counted: {inactive.reason}",
            )
        )
    if item.set_id is not None:
        components.append(
            ScoreComponent(
                key="set_bonus",
                label=f"Set: {item.set_name}" if item.set_name else f"Item set {item.set_id}",
                kind=ComponentKind.SET_BONUS,
                amount=0.0,
                effective_amount=0.0,
                weight=0.0,
                contribution=0.0,
                note="Not scored: version 1 does not value set bonuses",
            )
        )

    components.sort(key=lambda c: (-abs(c.contribution), c.kind != ComponentKind.STAT, c.label))
    score = sum(component.contribution for component in components)

    warnings, issues = _warnings(
        item, context, profile, ruleset, usable.reasons, amounts, caps, pools, derived_item
    )
    level = target_level(context, ruleset)
    assumptions = (
        f"Target: level {level} ({ruleset.content_mode(context.content_mode).label}).",
        (
            "Caps are measured from your current gear totals"
            + (" without the item being replaced." if replacing is not None else ".")
            if context.has_current_stats
            else "No current gear was given: caps are measured from zero."
        ),
        *(f"{stat_label(stat, ruleset)} cap: {info.derivation}." for stat, info in caps.items()),
        *profile.assumptions,
    )
    fingerprint = content_hash(
        {
            "item": item.version,
            "context": context.fingerprint,
            "profile": profile.content_hash,
            "ruleset": ruleset.content_hash,
            "engine": ENGINE_VERSION,
            "replacing": replacing.version if replacing is not None else None,
        }
    )
    return ScoreResult(
        item_id=item.id,
        item_name=item.name,
        item_version=item.version,
        item_provider=item.provenance.provider,
        item_data_version=item.provenance.data_version,
        score=score,
        score_unit=profile.score_unit,
        components=tuple(components),
        capped_stats=tuple(cap_events),
        threshold_events=tuple(threshold_events),
        warnings=tuple(warnings),
        assumptions=assumptions,
        eligible=usable.eligible,
        ineligibility=usable.reasons,
        profile_id=profile.id,
        profile_version=profile.version,
        profile_hash=profile.content_hash,
        ruleset_id=ruleset.id,
        ruleset_version=ruleset.version,
        ruleset_hash=ruleset.content_hash,
        engine_version=f"{ENGINE_VERSION} (package {package_version})",
        context_fingerprint=fingerprint,
        validation_status=profile.validation_status,
        confidence=_confidence(profile, issues),
    )


def _from_amount(part: AmountPart) -> _Part:
    if part.kind == ComponentKind.CONTEXT:
        key = f"context:{part.stat}"
    elif part.kind == ComponentKind.WEAPON:
        key = f"weapon:{part.stat}"
    else:
        key = f"stat:{part.stat}"
    return _Part(
        stat=part.stat,
        amount=part.amount,
        kind=part.kind,
        label=part.label,
        key=key,
        note=part.note,
    )


def _thresholds(
    profile: BuildProfile,
    ruleset: Ruleset,
    context: CharacterContext,
    pools: dict[Stat, list[_Part]],
    before_totals: dict[Stat, float],
    components: list[ScoreComponent],
) -> list[ThresholdEvent]:
    events = []
    for rule in profile.thresholds:
        amount = sum(part.amount for part in pools.get(rule.stat, []))
        if abs(amount) <= _EPSILON:
            continue
        evaluated = resolve_cap(rule.at, ruleset, context)
        before = before_totals.get(rule.stat, 0.0)
        after = before + amount
        target = evaluated.cap
        if before < target <= after:
            bonus, reached = rule.bonus, True
            message = f"Reaches {rule.label} ({target:g} from gear): +{rule.bonus:g}."
        elif after < target <= before:
            bonus, reached = -rule.bonus, False
            message = f"Drops below {rule.label} ({target:g} from gear): -{rule.bonus:g}."
        elif before >= target:
            bonus, reached = 0.0, True
            message = (
                f"{rule.label} is already reached with current gear ({before:g} of {target:g})."
            )
        else:
            bonus, reached = 0.0, False
            message = f"{target - after:g} short of {rule.label} ({after:g} of {target:g})."
        if not context.has_current_stats:
            message += " Give your current gear totals to check this breakpoint."
        events.append(
            ThresholdEvent(
                stat=rule.stat,
                label=rule.label,
                threshold=target,
                before=before,
                after=after,
                reached=reached,
                bonus=bonus,
                message=message + f" ({evaluated.derivation})",
            )
        )
        components.append(
            ScoreComponent(
                key=f"threshold:{rule.stat}:{rule.label}",
                label=rule.label,
                kind=ComponentKind.THRESHOLD,
                stat=rule.stat,
                amount=amount,
                effective_amount=amount,
                weight=0.0,
                contribution=bonus,
                note=message,
            )
        )
    return events


def _apply_exclusions(
    profile: BuildProfile, components: list[ScoreComponent]
) -> list[ScoreComponent]:
    """Within each exclusive group, only the stat with the largest contribution counts."""
    result = list(components)
    for group in profile.exclusive_groups:
        totals = {
            stat: sum(
                c.contribution
                for c in result
                if c.stat == stat and c.kind != ComponentKind.THRESHOLD
            )
            for stat in group.stats
        }
        present = {stat: total for stat, total in totals.items() if abs(total) > _EPSILON}
        if len(present) < 2:
            continue
        keep = max(present, key=lambda stat: present[stat])
        for index, component in enumerate(result):
            if (
                component.stat in present
                and component.stat != keep
                and component.kind != ComponentKind.THRESHOLD
            ):
                result[index] = component.model_copy(
                    update={
                        "effective_amount": 0.0,
                        "contribution": 0.0,
                        "note": f"Not counted: {group.note}",
                    }
                )
    return result


def _warnings(
    item: Item,
    context: CharacterContext,
    profile: BuildProfile,
    ruleset: Ruleset,
    ineligibility: tuple[str, ...],
    amounts: ItemAmounts,
    caps: dict[Stat, CapInfo],
    pools: dict[Stat, list[_Part]],
    derived_item: list[DerivedAmount],
) -> tuple[list[ScoreWarning], list[str]]:
    warnings: list[ScoreWarning] = []
    issues: list[str] = []
    if ineligibility:
        warnings.append(
            ScoreWarning(code="ineligible", message="Not usable: " + "; ".join(ineligibility))
        )
    sensitive = {stat for stat in caps} | {rule.stat for rule in profile.thresholds}
    touched = sorted(stat for stat in sensitive if stat in pools)
    if touched and not context.has_current_stats:
        names = ", ".join(stat_label(stat, ruleset) for stat in touched)
        warnings.append(
            ScoreWarning(
                code="cap_sensitive_without_current_stats",
                message=(
                    f"Cap-sensitive: {names} depend on what your other gear provides. No "
                    "current gear totals were given, so caps are measured from zero and this "
                    "recommendation may be approximate."
                ),
            )
        )
        issues.append("Current gear totals were not given for a cap-sensitive stat")
    if amounts.unscored:
        warnings.append(
            ScoreWarning(
                code="unscored_effects",
                message=f"{len(amounts.unscored)} effect(s) on this item are not scored: "
                "version 1 does not value procs or on-use effects.",
            )
        )
        issues.append("The item has effects that are not scored")
    if amounts.inactive:
        warnings.append(
            ScoreWarning(
                code="conditional_not_counted",
                message="; ".join(f"{i.effect.description} ({i.reason})" for i in amounts.inactive),
                severity="info",
            )
        )
    if derived_item and context.level != ruleset.conversions.level:
        warnings.append(
            ScoreWarning(
                code="conversions_at_other_level",
                message=(
                    f"Stat conversions are the ruleset's level-{ruleset.conversions.level} "
                    f"values; at level {context.level} they are approximate."
                ),
                severity="info",
            )
        )
        issues.append(f"Conversions are approximate at level {context.level}")
    if abs(context.level - profile.target_level) >= 10:
        warnings.append(
            ScoreWarning(
                code="profile_level",
                message=(
                    f"The {profile.label} profile was written for level {profile.target_level}; "
                    f"the character is level {context.level}."
                ),
            )
        )
        issues.append("The profile targets another level")
    if item.is_custom:
        warnings.append(
            ScoreWarning(
                code="custom_item",
                message="A custom item: its stats are as entered, not checked against the game.",
                severity="info",
            )
        )
    if item.set_id is not None:
        warnings.append(
            ScoreWarning(
                code="set_bonus_not_scored",
                message="Part of an item set: set bonuses are not scored in version 1.",
                severity="info",
            )
        )
    return warnings, issues
