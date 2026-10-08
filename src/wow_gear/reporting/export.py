"""Exports: a comparison or a gear analysis as JSON, as CSV, or as a shareable report.

JSON is the result model itself, so a file can be read back and checked; CSV is a table a
spreadsheet opens; the HTML report is one self-contained page - no scripts, nothing loaded
from elsewhere - that reads the same in light and dark mode and prints cleanly. Every
function formats; none changes a number.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Sequence
from html import escape

from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult, ExplanationLine
from wow_gear.models.enums import EquipmentSlot, Stat
from wow_gear.models.formatting import amount_text, number_text, signed_text, stat_label
from wow_gear.models.gear import CapStatus, GearAnalysis, ReplacementResult, SavedCharacter
from wow_gear.models.labels import CONTENT_MODE_LABELS, EQUIPMENT_SLOT_LABELS
from wow_gear.models.ruleset import Ruleset

DISCLAIMER = (
    "Recommended under the named build profile and its assumptions; another profile or "
    "other assumptions can change the answer. An unofficial fan tool: World of Warcraft is "
    "a trademark of Blizzard Entertainment."
)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _text_cell(value: str | None) -> str:
    """A text cell a spreadsheet will not run as a formula."""
    text = value or ""
    return "'" + text if text.startswith(_FORMULA_START) else text


def _cell(cell: object) -> object:
    """A number is written with two decimals - a number, never a formula; text is guarded."""
    if isinstance(cell, float):
        return f"{cell:.2f}"
    if isinstance(cell, str):
        return _text_cell(cell)
    return cell


def _csv(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(_cell(cell) for cell in row)
    return out.getvalue()


# --- comparisons ------------------------------------------------------------------------


def comparison_json(result: ComparisonResult) -> str:
    return result.model_dump_json(indent=2) + "\n"


def comparison_csv(result: ComparisonResult) -> str:
    """One row per item: its rank, score and status, with the profile it was scored under."""
    upgrades = {upgrade.item_id: upgrade.delta for upgrade in result.upgrades}
    return _csv(
        [
            "rank",
            "item_id",
            "item_name",
            "score",
            "unit",
            "status",
            "usable",
            "change_from_equipped",
            "profile_id",
            "profile_version",
            "ruleset_id",
            "ruleset_version",
            "fingerprint",
        ],
        (
            [
                item.rank or "",
                item.item_id,
                item.item_name,
                float(item.score),
                result.unit_abbreviation,
                item.recommendation_label or "",
                "yes" if item.eligible else "no",
                float(upgrades[item.item_id]) if item.item_id in upgrades else "",
                result.profile_id,
                result.profile_version,
                result.ruleset_id,
                result.ruleset_version,
                result.fingerprint,
            ]
            for item in result.results
        ),
    )


def components_csv(result: ComparisonResult) -> str:
    """Every item's score, component by component: amounts, weights and what each adds."""
    return _csv(
        [
            "item_id",
            "item_name",
            "component",
            "kind",
            "stat",
            "amount",
            "counted",
            "weight",
            "value",
            "note",
        ],
        (
            [
                item.item_id,
                item.item_name,
                component.label,
                component.kind.value,
                component.stat.value if component.stat else "",
                float(component.amount),
                float(component.effective_amount),
                float(component.weight),
                float(component.contribution),
                component.note or "",
            ]
            for item in result.results
            for component in item.components
        ),
    )


# --- gear -------------------------------------------------------------------------------


def character_json(character: SavedCharacter) -> str:
    """A saved character with its gear: the file a gear import reads back."""
    return character.model_dump_json(indent=2) + "\n"


def analysis_json(analysis: GearAnalysis) -> str:
    return analysis.model_dump_json(indent=2) + "\n"


def gear_csv(character: SavedCharacter, analysis: GearAnalysis | None = None) -> str:
    """Every slot, worn or empty: the gear list a CSV gear import reads back."""
    values = {value.slot: value for value in analysis.slots} if analysis else {}
    rows = []
    for slot in EquipmentSlot:
        value = values.get(slot)
        rows.append(
            [
                slot.value,
                character.gear.items.get(slot, ""),
                value.item_name if value else "",
                value.item_level if value and value.item_level is not None else "",
                float(value.score) if value else "",
            ]
        )
    unit = analysis.unit_abbreviation if analysis else "score"
    column = "value_" + (re.sub(r"[^a-z0-9]+", "_", unit.lower()).strip("_") or "score")
    return _csv(["slot", "item_id", "item_name", "item_level", column], rows)


# --- the HTML report --------------------------------------------------------------------

_STYLE = """
:root { color-scheme: light dark; --bg: #f7f5f0; --panel: #ffffff; --text: #1d232b;
  --muted: #5c6470; --line: #e3ded3; --accent: #8f6516; --good: #2f7d4f; --bad: #a33a32; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0f141c; --panel: #161d28; --text: #e6e8ec; --muted: #9aa3b0;
    --line: #2a3442; --accent: #d2a54e; --good: #6cc08f; --bad: #e07a70; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 880px; margin: 0 auto; padding: 32px 16px 48px; }
h1, h2 { font-family: Georgia, "Times New Roman", serif; font-weight: 600; line-height: 1.25; }
h1 { font-size: 1.6rem; margin: 0 0 4px; }
h2 { font-size: 1.1rem; margin: 28px 0 8px; color: var(--accent); }
.eyebrow { text-transform: uppercase; letter-spacing: .08em; font-size: .72rem;
  color: var(--muted); margin: 0 0 6px; }
.meta { color: var(--muted); font-size: .9rem; margin: 0 0 16px; }
.headline { background: var(--panel); border: 1px solid var(--line);
  border-left: 4px solid var(--accent); border-radius: 8px; padding: 14px 16px; margin: 16px 0; }
.headline p { margin: 0; }
.headline .why { color: var(--muted); margin-top: 6px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: var(--panel);
  border: 1px solid var(--line); border-radius: 8px; font-size: .92rem; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--line); text-align: left;
  vertical-align: top; }
th { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: var(--good); } .down { color: var(--bad); }
ul { margin: 6px 0; padding-left: 20px; }
li { margin: 3px 0; }
.small { color: var(--muted); font-size: .85rem; }
footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: .8rem; }
@media (max-width: 560px) { main { padding: 20px 12px 32px; } table { font-size: .84rem; }
  th, td { padding: 6px 6px; } th { letter-spacing: .02em; } }
@media print { body { background: #fff; color: #000; } table, .headline { break-inside: avoid; } }
"""


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n<style>{_STYLE}</style>\n</head>\n"
        f"<body><main>\n{body}\n<footer>{escape(DISCLAIMER)}</footer>\n</main></body>\n</html>\n"
    )


def _table(header: Sequence[str], rows: Iterable[Sequence[str]], numeric: set[int]) -> str:
    """A table from cells that are already escaped HTML."""

    def cell(tag: str, index: int, content: str) -> str:
        css = ' class="num"' if index in numeric else ""
        return f"<{tag}{css}>{content}</{tag}>"

    head = "".join(cell("th", index, escape(text)) for index, text in enumerate(header))
    body = "".join(
        "<tr>" + "".join(cell("td", index, text) for index, text in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _signed(value: float) -> str:
    css = "up" if value > 0.05 else "down" if value < -0.05 else ""
    text = signed_text(value)
    return f'<span class="{css}">{text}</span>' if css else text


def _list(title: str, entries: Sequence[str]) -> str:
    if not entries:
        return ""
    items = "".join(f"<li>{escape(entry)}</li>" for entry in entries)
    return f"<h2>{escape(title)}</h2><ul>{items}</ul>"


def _context_text(context: CharacterContext) -> str:
    parts = [
        f"Level {context.level}",
        f"phase {context.phase}",
        CONTENT_MODE_LABELS[context.content_mode],
    ]
    if context.race is not None:
        parts.append(context.race.value.replace("_", " ").title())
    if context.target_level is not None:
        parts.append(f"target level {context.target_level}")
    parts.append(
        "current gear totals given" if context.has_current_stats else "no current gear totals"
    )
    return ", ".join(parts)


def _lines_table(lines: Sequence[ExplanationLine], first: str, second: str, unit: str) -> str:
    return _table(
        ["Component", f"{first} ({unit})", f"{second} ({unit})", "Difference"],
        (
            [
                escape(line.label)
                + (f'<div class="small">{escape(line.note)}</div>' if line.note else ""),
                f"{line.first_value:.1f}",
                f"{line.second_value:.1f}",
                _signed(line.delta),
            ]
            for line in lines
        ),
        numeric={1, 2, 3},
    )


def comparison_html(result: ComparisonResult, context: CharacterContext | None = None) -> str:
    """A shareable report of a comparison: the answer, why, and everything it rests on."""
    unit = result.unit_abbreviation
    parts = [
        '<p class="eyebrow">Classic Gear Calculator · item comparison</p>',
        f"<h1>{escape(result.profile_label)}</h1>",
        f'<p class="meta">Profile {escape(result.profile_id)} {escape(result.profile_version)}'
        f" · ruleset {escape(result.ruleset_id)} {escape(result.ruleset_version)}"
        f" · scores in {escape(result.score_unit)}"
        + (f"<br>{escape(_context_text(context))}" if context is not None else "")
        + "</p>",
        '<div class="headline">'
        f"<p><strong>{escape(result.headline)}</strong></p>"
        + (f'<p class="why">Why: {escape(result.why)}.</p>' if result.why else "")
        + "</div>",
        "<h2>Ranking</h2>",
        _table(
            ["#", "Item", f"Score ({unit})", "Status"],
            (
                [
                    str(item.rank or ""),
                    escape(item.item_name),
                    f"{item.score:.1f}",
                    escape(item.recommendation_label or ""),
                ]
                for item in result.results
            ),
            numeric={0, 2},
        ),
    ]
    if result.lines and result.first_id and result.second_id:
        first = result.result(result.first_id).item_name
        second = result.result(result.second_id).item_name
        parts += [
            "<h2>Where the difference comes from</h2>",
            _lines_table(result.lines, first, second, unit),
        ]
    if result.upgrades and result.replaced is not None:
        parts += [
            f"<h2>Against the equipped {escape(result.replaced.item_name)}</h2>",
            _table(
                ["Item", f"Change ({unit})"],
                ([escape(u.item_name), _signed(u.delta)] for u in result.upgrades),
                numeric={1},
            ),
        ]
    parts.append(_list("Not valued by this profile", result.not_valued))
    parts.append(_list("Not scored in version 1", result.not_scored))
    parts.append(_list("Notes", result.notes))
    if result.results:
        parts.append(_list("Assumptions", result.results[0].assumptions))
    reasons = "; ".join(result.confidence.reasons)
    parts.append(
        f'<p class="small">Confidence: {escape(result.confidence.level)}'
        + (f" ({escape(reasons)})" if reasons else "")
        + f". Fingerprint {escape(result.fingerprint)}: the same items, context and profile "
        "give the same fingerprint and the same scores.</p>"
    )
    return _page(f"Comparison - {result.profile_label}", "\n".join(part for part in parts if part))


def _caps_table(caps: Sequence[CapStatus]) -> str:
    def amount(status: CapStatus, value: float) -> str:
        return f"{number_text(value)}{'%' if status.percent else ''}"

    states = {"short": "Short", "reached": "Reached", "over": "Over"}
    return _table(
        ["Cap or breakpoint", "From gear", "Target", "State"],
        (
            [
                escape(status.label) + f'<div class="small">{escape(status.message)}</div>',
                amount(status, round(status.total, 2)),
                amount(status, round(status.target, 2)),
                states[status.state],
            ]
            for status in caps
        ),
        numeric={1, 2},
    )


def _stat_text(stat: Stat, value: float, ruleset: Ruleset) -> tuple[str, str]:
    return stat_label(stat, ruleset), amount_text(stat, value, ruleset)


def gear_html(
    character: SavedCharacter,
    analysis: GearAnalysis,
    ruleset: Ruleset,
    replacement: ReplacementResult | None = None,
) -> str:
    """A shareable report of a character's gear: its value, piece by piece, and its caps."""
    unit = analysis.unit_abbreviation
    names = {value.slot: value for value in analysis.slots}
    parts = [
        '<p class="eyebrow">Classic Gear Calculator · gear set</p>',
        f"<h1>{escape(character.name)}</h1>",
        f'<p class="meta">{escape(character.class_name.value.title())}, level {character.level}'
        f" · phase {character.phase} · {escape(CONTENT_MODE_LABELS[character.content_mode])}"
        f"<br>Profile {escape(analysis.profile_id)} {escape(analysis.profile_version)}"
        f" · ruleset {escape(analysis.ruleset_id)} {escape(analysis.ruleset_version)}"
        f" · scores in {escape(analysis.score_unit)}</p>",
        '<div class="headline">'
        f"<p><strong>This gear is worth {analysis.score:.1f} {escape(unit)} under the profile."
        "</strong></p>"
        '<p class="why">A piece is worth what the character would lose without it, with the '
        "rest of the gear as it is.</p></div>",
        "<h2>Gear</h2>",
        _table(
            ["Slot", "Item", "Item level", f"Worth ({unit})"],
            (
                [
                    escape(EQUIPMENT_SLOT_LABELS[slot]),
                    escape(names[slot].item_name)
                    if slot in names
                    else '<span class="small">Empty</span>',
                    str(names[slot].item_level or "") if slot in names else "",
                    f"{names[slot].score:.1f}" if slot in names else "",
                ]
                for slot in EquipmentSlot
            ),
            numeric={2, 3},
        ),
        "<h2>Where the value comes from</h2>",
        _table(
            ["Component", "Amount", f"Value ({unit})"],
            (
                [
                    escape(component.label),
                    number_text(component.amount),
                    f"{component.contribution:.1f}",
                ]
                for component in analysis.components
                if abs(component.contribution) > 0.005
            ),
            numeric={1, 2},
        ),
        "<h2>Totals from gear</h2>",
        _table(
            ["Stat", "Total"],
            (
                [escape(label), escape(amount)]
                for label, amount in (
                    _stat_text(stat, value, ruleset) for stat, value in analysis.totals.items()
                )
            ),
            numeric={1},
        ),
    ]
    if analysis.caps:
        parts += ["<h2>Caps and breakpoints</h2>", _caps_table(analysis.caps)]
    parts.append(_list("Under-served priorities", analysis.under_served))
    parts.append(_list("Not valued by this profile", analysis.not_valued))
    parts.append(
        _list(
            "Weakest pieces",
            [
                f"{w.item_name} ({EQUIPMENT_SLOT_LABELS[w.slot]}): {w.reason}"
                for w in analysis.weakest
            ],
        )
    )
    parts.append(_list("Not scored in version 1", analysis.not_scored))
    parts.append(_list("Notes", analysis.notes))
    parts.append(_list("Assumptions", analysis.assumptions))
    if replacement is not None:
        removed = " and ".join(replacement.removed) or "nothing"
        parts += [
            f"<h2>Trying {escape(replacement.candidate_name)}</h2>",
            f"<p>In the {escape(EQUIPMENT_SLOT_LABELS[replacement.slot].lower())} slot, replacing "
            f"{escape(removed)}: <strong>{_signed(replacement.delta)} {escape(unit)}</strong> "
            f"({replacement.score_before:.1f} to {replacement.score_after:.1f}).</p>",
            _lines_table(replacement.lines, "With it", "Now", unit) if replacement.lines else "",
            _list("Notes on this change", replacement.notes),
        ]
    parts.append(
        f'<p class="small">Fingerprint {escape(analysis.fingerprint)}: the same gear, character '
        "and profile give the same fingerprint and the same values.</p>"
    )
    return _page(f"Gear - {character.name}", "\n".join(part for part in parts if part))
