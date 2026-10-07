"""A comparison as plain text, for the command line and for sharing. It formats; it never
changes a number."""

from __future__ import annotations

from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.enums import EquipmentSlot
from wow_gear.models.gear import GearAnalysis, ReplacementResult, SavedCharacter
from wow_gear.models.labels import CONTENT_MODE_LABELS, EQUIPMENT_SLOT_LABELS


def _table(rows: list[list[str]], right: set[int]) -> list[str]:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = []
    for row in rows:
        cells = [
            cell.rjust(widths[column]) if column in right else cell.ljust(widths[column])
            for column, cell in enumerate(row)
        ]
        lines.append("  ".join(cells).rstrip())
    return lines


def comparison_text(result: ComparisonResult) -> str:
    unit = result.unit_abbreviation
    out = [
        result.headline,
        f"Profile: {result.profile_label}, {result.profile_id} {result.profile_version}; "
        f"ruleset {result.ruleset_id} {result.ruleset_version}; scores in {result.score_unit}.",
    ]
    if result.why:
        out.append(f"Why: {result.why}.")
    out.append("")

    ranking = [["#", "Item", f"Score ({unit})", "Status"]]
    for item in result.results:
        ranking.append(
            [
                str(item.rank),
                item.item_name,
                f"{item.score:.1f}",
                item.recommendation_label or "",
            ]
        )
    out.extend(_table(ranking, right={0, 2}))

    if result.lines and result.first_id and result.second_id:
        first = result.result(result.first_id).item_name
        second = result.result(result.second_id).item_name
        rows = [["Component", first, second, "Difference"]]
        for line in result.lines:
            rows.append(
                [
                    line.label,
                    f"{line.first_value:.1f}",
                    f"{line.second_value:.1f}",
                    f"{line.delta:+.1f}",
                ]
            )
        out.append("")
        out.extend(_table(rows, right={1, 2, 3}))
        notes = [f"{line.label}: {line.note}" for line in result.lines if line.note]
        out.extend(f"  {note}" for note in notes)

    if result.upgrades:
        assert result.replaced is not None
        out.append("")
        out.append(f"Against the equipped {result.replaced.item_name}:")
        for upgrade in result.upgrades:
            out.append(f"  {upgrade.item_name}: {upgrade.delta:+.1f} {unit}")

    out.append("")
    if result.not_valued:
        out.append(f"Not valued by this profile: {', '.join(result.not_valued)}.")
    for effect in result.not_scored:
        out.append(f"Not scored in version 1: {effect}")
    for note in result.notes:
        out.append(f"Note: {note}")
    reasons = "; ".join(result.confidence.reasons)
    out.append(f"Confidence: {result.confidence.level}" + (f" ({reasons})." if reasons else "."))
    out.append(
        f"Recommended under this profile and these assumptions; fingerprint {result.fingerprint}."
    )
    return "\n".join(out)


def gear_text(
    character: SavedCharacter,
    analysis: GearAnalysis,
    replacement: ReplacementResult | None = None,
) -> str:
    """A character's gear analysis as plain text, with a replacement being tried if any."""
    unit = analysis.unit_abbreviation
    out = [
        f"{character.name}: level {character.level} {character.class_name.value}, phase "
        f"{character.phase}, {CONTENT_MODE_LABELS[character.content_mode]}.",
        f"Profile {analysis.profile_id} {analysis.profile_version}; ruleset "
        f"{analysis.ruleset_id} {analysis.ruleset_version}; values in {analysis.score_unit}.",
        f"This gear is worth {analysis.score:.1f} {unit}. A piece is worth what the character "
        "would lose without it.",
        "",
    ]
    values = {value.slot: value for value in analysis.slots}
    rows = [["Slot", "Item", "Item level", f"Worth ({unit})"]]
    for slot in EquipmentSlot:
        value = values.get(slot)
        rows.append(
            [
                EQUIPMENT_SLOT_LABELS[slot],
                value.item_name if value else "-",
                str(value.item_level or "") if value else "",
                f"{value.score:.1f}" if value else "",
            ]
        )
    out.extend(_table(rows, right={2, 3}))
    if analysis.caps:
        out.append("")
        out.append("Caps and breakpoints:")
        out.extend(
            f"  {status.label} ({status.state}): {status.message}" for status in analysis.caps
        )
    sections = (
        ("Under-served priorities", analysis.under_served),
        ("Not valued by this profile", analysis.not_valued),
        (
            "Weakest pieces",
            tuple(
                f"{EQUIPMENT_SLOT_LABELS[w.slot]} - {w.item_name}: {w.reason}"
                for w in analysis.weakest
            ),
        ),
        ("Not scored in version 1", analysis.not_scored),
        ("Notes", analysis.notes),
    )
    for title, entries in sections:
        if entries:
            out.append("")
            out.append(f"{title}:")
            out.extend(f"  {entry}" for entry in entries)
    if replacement is not None:
        removed = " and ".join(replacement.removed) or "nothing"
        out.append("")
        out.append(
            f"Trying {replacement.candidate_name} in the "
            f"{EQUIPMENT_SLOT_LABELS[replacement.slot].lower()} slot (replacing {removed}): "
            f"{replacement.delta:+.1f} {unit} ({replacement.score_before:.1f} to "
            f"{replacement.score_after:.1f})."
        )
        out.extend(f"  {line.text}" for line in replacement.lines)
        out.extend(f"  Note: {note}" for note in replacement.notes)
    out.append("")
    out.append(
        f"Valued under this profile and its assumptions; fingerprint {analysis.fingerprint}."
    )
    return "\n".join(out)
