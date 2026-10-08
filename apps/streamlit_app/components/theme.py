"""The design system: colour tokens for light and dark, and the CSS the components use.

Streamlit's own widgets take their colours from ``.streamlit/config.toml``; these tokens style
the few custom elements (cards, chips, score tiles, deltas) to match. Green is only for a
beneficial difference, red only for a harmful one, gold for what is selected or recommended -
and every one of them also carries a sign or an arrow, so colour is never the only signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Tokens:
    text: str
    muted: str
    border: str
    surface: str
    surface_alt: str
    navy: str
    gold: str
    gold_soft: str
    good: str
    good_soft: str
    bad: str
    bad_soft: str
    neutral_soft: str
    quality: dict[str, str]


LIGHT = Tokens(
    text="#1E2633",
    muted="#5B6472",
    border="#D6CFC1",
    surface="#FFFFFF",
    surface_alt="#F1EEE7",
    navy="#23426E",
    gold="#8F6516",
    gold_soft="rgba(176, 128, 30, 0.13)",
    good="#2E7D4F",
    good_soft="rgba(46, 125, 79, 0.11)",
    bad="#B3261E",
    bad_soft="rgba(179, 38, 30, 0.09)",
    neutral_soft="rgba(107, 114, 128, 0.12)",
    quality={
        "poor": "#7A7A7A",
        "common": "#4B5563",
        "uncommon": "#2D8A1E",
        "rare": "#0B63C4",
        "epic": "#8A3FD1",
        "legendary": "#C26A00",
    },
)

DARK = Tokens(
    text="#E8E4DA",
    muted="#A2A9B4",
    border="#2A3445",
    surface="#151C27",
    surface_alt="#1B2433",
    navy="#9CB8E4",
    gold="#D2A54E",
    gold_soft="rgba(210, 165, 78, 0.16)",
    good="#5DBB86",
    good_soft="rgba(93, 187, 134, 0.14)",
    bad="#EE6A60",
    bad_soft="rgba(238, 106, 96, 0.13)",
    neutral_soft="rgba(139, 147, 161, 0.16)",
    quality={
        "poor": "#9D9D9D",
        "common": "#D7D7D7",
        "uncommon": "#4FD33A",
        "rare": "#3D9BFF",
        "epic": "#B57CF2",
        "legendary": "#FF9A2E",
    },
)


def tokens() -> Tokens:
    """The tokens for the theme the browser shows (light unless it reports dark)."""
    theme = getattr(st.context, "theme", None)
    return DARK if getattr(theme, "type", None) == "dark" else LIGHT


def _css(t: Tokens) -> str:
    quality = "\n".join(
        f".wg-q-{name} {{ color: {colour}; }}" for name, colour in t.quality.items()
    )
    return f"""
<style>
:root {{
  --wg-text: {t.text}; --wg-muted: {t.muted}; --wg-border: {t.border};
  --wg-surface: {t.surface}; --wg-surface-alt: {t.surface_alt}; --wg-navy: {t.navy};
  --wg-gold: {t.gold}; --wg-gold-soft: {t.gold_soft};
  --wg-good: {t.good}; --wg-good-soft: {t.good_soft};
  --wg-bad: {t.bad}; --wg-bad-soft: {t.bad_soft}; --wg-neutral-soft: {t.neutral_soft};
}}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px; }}
.wg-brand {{ display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap; }}
.wg-brand h1 {{ margin: 0; padding: 0; font-size: 1.85rem; }}
.wg-brand .wg-tagline {{ color: var(--wg-muted); font-size: 0.95rem; }}
.wg-eyebrow {{ text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem;
  color: var(--wg-muted); font-weight: 600; margin-bottom: 0.15rem; }}
.wg-crumbs {{ color: var(--wg-muted); font-size: 0.92rem; line-height: 1.6; }}
.wg-crumbs b {{ color: var(--wg-text); font-weight: 600; }}
.wg-crumbs .wg-sep {{ color: var(--wg-gold); padding: 0 0.3rem; }}
.wg-chips {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.35rem 0 0.2rem 0; }}
.wg-chip {{ display: inline-flex; align-items: center; gap: 0.25rem; border-radius: 999px;
  padding: 0.1rem 0.6rem; font-size: 0.8rem; line-height: 1.5; white-space: nowrap;
  background: var(--wg-neutral-soft); color: var(--wg-text);
  font-variant-numeric: tabular-nums; }}
.wg-chip.wg-good {{ background: var(--wg-good-soft); color: var(--wg-good); }}
.wg-chip.wg-bad {{ background: var(--wg-bad-soft); color: var(--wg-bad); }}
.wg-chip.wg-gold {{ background: var(--wg-gold-soft); color: var(--wg-gold); font-weight: 600; }}
.wg-chip.wg-muted {{ color: var(--wg-muted); }}
.wg-item-name {{ font-weight: 650; font-size: 1.05rem; line-height: 1.3; }}
.wg-item-meta {{ color: var(--wg-muted); font-size: 0.85rem; }}
.wg-item-meta a {{ color: var(--wg-navy); }}
.wg-dot {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%;
  margin-right: 0.35rem; vertical-align: 0.05rem; background: currentColor; }}
.wg-verdict {{ border-left: 4px solid var(--wg-gold); padding: 0.2rem 0 0.2rem 0.9rem; }}
.wg-verdict.wg-neutral {{ border-left-color: var(--wg-muted); }}
.wg-verdict .wg-winner {{ font-family: "Source Serif Pro", "Source Serif 4", serif;
  font-size: 1.6rem; font-weight: 700; line-height: 1.25; }}
.wg-verdict .wg-sub {{ color: var(--wg-muted); margin-top: 0.15rem; }}
.wg-tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.6rem; margin: 0.9rem 0 0.4rem 0; }}
.wg-tile {{ border: 1px solid var(--wg-border); border-radius: 0.6rem; padding: 0.6rem 0.8rem;
  background: var(--wg-surface); }}
.wg-tile.wg-picked {{ border-color: var(--wg-gold); box-shadow: inset 0 0 0 1px var(--wg-gold); }}
.wg-tile .wg-tile-label {{ color: var(--wg-muted); font-size: 0.78rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }}
.wg-tile .wg-tile-value {{ font-size: 1.75rem; font-weight: 650; line-height: 1.2;
  font-variant-numeric: tabular-nums; }}
.wg-tile .wg-tile-unit {{ color: var(--wg-muted); font-size: 0.8rem; margin-left: 0.2rem; }}
.wg-delta-good {{ color: var(--wg-good); }}
.wg-delta-bad {{ color: var(--wg-bad); }}
.wg-why {{ list-style: none; padding: 0; margin: 0.2rem 0 0 0; }}
.wg-why li {{ display: grid; grid-template-columns: 6.2rem 1fr; gap: 0.6rem;
  align-items: baseline; padding: 0.32rem 0; border-bottom: 1px dashed var(--wg-border); }}
.wg-why li:last-child {{ border-bottom: none; }}
.wg-why .wg-amount {{ font-variant-numeric: tabular-nums; font-weight: 650; text-align: right;
  white-space: nowrap; }}
.wg-why .wg-note {{ color: var(--wg-muted); font-size: 0.85rem; }}
.wg-empty {{ border: 1px dashed var(--wg-border); border-radius: 0.7rem; padding: 1.4rem;
  color: var(--wg-muted); text-align: left; }}
.wg-empty b {{ color: var(--wg-text); }}
.wg-empty ol {{ margin: 0.5rem 0 0 1.1rem; padding: 0; }}
.wg-small {{ color: var(--wg-muted); font-size: 0.84rem; }}
.wg-assume {{ color: var(--wg-gold); font-weight: 600; font-size: 0.86rem; }}
.wg-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; margin: 0.4rem 0; }}
.wg-table th {{ text-align: left; color: var(--wg-muted); font-weight: 600;
  border-bottom: 1px solid var(--wg-border); padding: 0.35rem 0.5rem; }}
.wg-table td {{ border-bottom: 1px solid var(--wg-border); padding: 0.4rem 0.5rem;
  vertical-align: top; }}
.wg-table .wg-num {{ text-align: right; font-variant-numeric: tabular-nums;
  white-space: nowrap; }}
.wg-slot {{ min-width: 0; }}
.wg-slot-top {{ display: flex; justify-content: space-between; align-items: center;
  gap: 0.4rem; min-height: 1.5rem; }}
.wg-slot-top .wg-eyebrow {{ margin-bottom: 0; }}
.wg-slot-top .wg-chip {{ font-size: 0.75rem; padding: 0 0.5rem; }}
.wg-slot-meta {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.wg-slot-name {{ font-weight: 600; line-height: 1.3; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }}
.wg-slot-none {{ color: var(--wg-muted); font-weight: 400; font-style: italic; }}
.wg-bar {{ height: 0.38rem; border-radius: 999px; background: var(--wg-neutral-soft);
  overflow: hidden; margin: 0.3rem 0 0.25rem 0; }}
.wg-bar > span {{ display: block; height: 100%; border-radius: inherit;
  background: var(--wg-gold); }}
.wg-bar.wg-good > span {{ background: var(--wg-good); }}
.wg-bar.wg-bad > span {{ background: var(--wg-bad); }}
.wg-cap {{ padding: 0.5rem 0; border-bottom: 1px dashed var(--wg-border); }}
.wg-cap:last-child {{ border-bottom: none; }}
.wg-cap-head {{ display: flex; justify-content: space-between; align-items: baseline;
  gap: 0.5rem; flex-wrap: wrap; }}
@media (max-width: 640px) {{
  /* A wide table scrolls inside itself; columns keep a readable width. */
  .wg-table {{ display: block; overflow-x: auto; }}
  .wg-table th, .wg-table td {{ min-width: 6.5rem; overflow-wrap: break-word; }}
  .wg-table .wg-num {{ min-width: 3.5rem; }}
  .wg-table td:last-child:not(.wg-num) {{ min-width: 15rem; }}
}}
.wg-list {{ margin: 0.2rem 0 0.4rem 1.1rem; padding: 0; }}
.wg-list li {{ margin: 0.15rem 0; }}
{quality}
</style>
"""


def inject() -> Tokens:
    """Add the stylesheet to the page and return the tokens in use."""
    t = tokens()
    st.html(_css(t))
    return t
