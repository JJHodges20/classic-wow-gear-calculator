"""The design system: colour tokens for light and dark, the spacing and type scales, and the
CSS the components use.

Streamlit's own widgets take their colours, fonts and corners from ``.streamlit/config.toml``;
these tokens style the custom elements (page headers, cards, tiles, tables, notes) to match.
Green is only for a beneficial difference, red only for a harmful one, gold for what is
selected or recommended, navy for links and information - and every one of them also
carries a word, a sign or an arrow, so colour is never the only signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Tokens:
    text: str
    text_2: str
    muted: str
    border: str
    border_strong: str
    background: str
    surface: str
    surface_alt: str
    row_hover: str
    navy: str
    gold: str
    gold_soft: str
    on_gold: str
    good: str
    good_soft: str
    bad: str
    bad_soft: str
    warning: str
    warning_soft: str
    neutral_soft: str
    shadow: str
    quality: dict[str, str]


LIGHT = Tokens(
    text="#1C2430",
    text_2="#3D4654",
    muted="#646B78",
    border="#E2DCD0",
    border_strong="#CFC7B8",
    background="#F6F4EF",
    surface="#FFFFFF",
    surface_alt="#F6F3EC",
    row_hover="rgba(143, 101, 22, 0.045)",
    navy="#23426E",
    gold="#8F6516",
    gold_soft="rgba(176, 128, 30, 0.12)",
    on_gold="#FFFFFF",
    good="#2E7D4F",
    good_soft="rgba(46, 125, 79, 0.10)",
    bad="#B3261E",
    bad_soft="rgba(179, 38, 30, 0.08)",
    warning="#A35A12",
    warning_soft="rgba(163, 90, 18, 0.10)",
    neutral_soft="rgba(100, 107, 120, 0.10)",
    shadow="0 1px 2px rgba(28, 36, 48, 0.04), 0 1px 3px rgba(28, 36, 48, 0.06)",
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
    text_2="#C3C8D0",
    muted="#8F98A6",
    border="#263040",
    border_strong="#344054",
    background="#0E131B",
    surface="#151C27",
    surface_alt="#1A2230",
    row_hover="rgba(210, 165, 78, 0.06)",
    navy="#9CB8E4",
    gold="#D2A54E",
    gold_soft="rgba(210, 165, 78, 0.15)",
    on_gold="#0E131B",
    good="#5DBB86",
    good_soft="rgba(93, 187, 134, 0.13)",
    bad="#EE6A60",
    bad_soft="rgba(238, 106, 96, 0.12)",
    warning="#E39A4F",
    warning_soft="rgba(227, 154, 79, 0.13)",
    neutral_soft="rgba(143, 152, 166, 0.14)",
    shadow="0 1px 2px rgba(0, 0, 0, 0.30), 0 1px 3px rgba(0, 0, 0, 0.22)",
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
  --wg-text: {t.text}; --wg-text-2: {t.text_2}; --wg-muted: {t.muted};
  --wg-border: {t.border}; --wg-border-strong: {t.border_strong};
  --wg-bg: {t.background}; --wg-surface: {t.surface}; --wg-surface-alt: {t.surface_alt};
  --wg-row-hover: {t.row_hover}; --wg-navy: {t.navy};
  --wg-gold: {t.gold}; --wg-gold-soft: {t.gold_soft}; --wg-on-gold: {t.on_gold};
  --wg-good: {t.good}; --wg-good-soft: {t.good_soft};
  --wg-bad: {t.bad}; --wg-bad-soft: {t.bad_soft};
  --wg-warning: {t.warning}; --wg-warning-soft: {t.warning_soft};
  --wg-neutral-soft: {t.neutral_soft}; --wg-shadow: {t.shadow};
  /* Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 */
  --wg-s1: 4px; --wg-s2: 8px; --wg-s3: 12px; --wg-s4: 16px;
  --wg-s5: 24px; --wg-s6: 32px; --wg-s7: 48px;
  --wg-radius: 12px; --wg-radius-sm: 8px;
}}

/* ---- Page frame ------------------------------------------------------------------- */
/* The top bar is 56px tall; content starts 24px below it. */
.block-container {{ padding-top: 5.35rem; padding-bottom: var(--wg-s6);
  max-width: 1280px; }}
[data-testid="stHeader"] {{ border-bottom: 1px solid var(--wg-border); }}
.stMainBlockContainer a, .wg-link {{ color: var(--wg-navy); text-decoration: none;
  font-weight: 500; }}
.stMainBlockContainer a:hover {{ text-decoration: underline; text-underline-offset: 2px; }}
.stMainBlockContainer a:focus-visible {{ outline: 2px solid var(--wg-gold);
  outline-offset: 2px; border-radius: 3px; }}
/* The page links show where the keyboard is, not only a faint background. */
[data-testid="stTopNavLink"]:focus-visible,
[data-testid="stSidebarNavLink"]:focus-visible {{ outline: 2px solid var(--wg-gold);
  outline-offset: 2px; }}

/* ---- Page header and sections ------------------------------------------------------- */
.wg-page-header {{ display: flex; align-items: flex-start; gap: var(--wg-s4);
  margin-bottom: var(--wg-s1); }}
.wg-page-icon {{ flex: 0 0 auto; width: 40px; height: 40px; border-radius: 10px;
  background: var(--wg-gold-soft); color: var(--wg-gold); display: flex;
  align-items: center; justify-content: center; margin-top: 2px; }}
.wg-page-icon img {{ width: 22px; height: 22px; display: block; }}
.wg-page-title {{ font-size: 1.75rem; font-weight: 700; letter-spacing: -0.015em;
  line-height: 1.2; margin: 0; padding: 0; color: var(--wg-text); }}
.wg-page-lede {{ color: var(--wg-muted); font-size: 0.95rem; line-height: 1.5;
  margin: var(--wg-s1) 0 0 0; max-width: 72ch; }}
.wg-section {{ display: flex; align-items: baseline; gap: var(--wg-s2) var(--wg-s3);
  flex-wrap: wrap; margin-top: var(--wg-s3); }}
.wg-section-title {{ font-size: 1.05rem; font-weight: 650; letter-spacing: -0.005em;
  margin: 0; padding: 0; color: var(--wg-text); line-height: 1.3; }}
.wg-section-aside {{ color: var(--wg-muted); font-size: 0.85rem; }}
.wg-section-desc {{ flex-basis: 100%; color: var(--wg-muted); font-size: 0.875rem;
  margin: 0; line-height: 1.45; }}
.wg-eyebrow {{ text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.7rem;
  color: var(--wg-muted); font-weight: 650; margin-bottom: var(--wg-s1); }}
.wg-crumbs {{ color: var(--wg-muted); font-size: 0.875rem; line-height: 1.6; }}
.wg-crumbs b {{ color: var(--wg-text); font-weight: 600; }}
.wg-crumbs .wg-sep {{ color: var(--wg-gold); padding: 0 0.3rem; }}
.wg-footer {{ border-top: 1px solid var(--wg-border); margin-top: var(--wg-s6);
  padding-top: var(--wg-s4); color: var(--wg-muted); font-size: 0.8rem; line-height: 1.5; }}

/* ---- Cards: one per logical panel; Streamlit's bordered containers with a wg-card key */
[class*="st-key-wg-card"] {{ background: var(--wg-surface);
  border-color: var(--wg-border) !important; border-radius: var(--wg-radius) !important;
  box-shadow: var(--wg-shadow); }}
[class*="st-key-wg-inset"] {{ background: var(--wg-surface-alt);
  border-color: var(--wg-border) !important; border-radius: 10px !important; }}
[data-testid="stExpander"] details {{ background: var(--wg-surface);
  border-color: var(--wg-border); border-radius: var(--wg-radius); }}
[data-testid="stExpander"] summary p {{ font-weight: 600; }}

/* ---- Buttons: the label on the gold fill keeps 4.5:1 in both schemes ---------------- */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primary"] * {{ color: var(--wg-on-gold) !important; }}

/* ---- Chips, item cards, verdicts ------------------------------------------------------ */
.wg-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 4px 0; }}
.wg-chip {{ display: inline-flex; align-items: center; gap: 0.25rem; border-radius: 999px;
  padding: 1px 10px; font-size: 0.78rem; line-height: 1.55; white-space: nowrap;
  background: var(--wg-neutral-soft); color: var(--wg-text-2); font-weight: 500;
  font-variant-numeric: tabular-nums; }}
.wg-chip.wg-good {{ background: var(--wg-good-soft); color: var(--wg-good); }}
.wg-chip.wg-bad {{ background: var(--wg-bad-soft); color: var(--wg-bad); }}
.wg-chip.wg-gold {{ background: var(--wg-gold-soft); color: var(--wg-gold); font-weight: 650; }}
.wg-chip.wg-muted {{ color: var(--wg-muted); }}
.wg-card-title {{ font-size: 1.2rem; font-weight: 650; letter-spacing: -0.01em;
  line-height: 1.3; margin: 0 0 var(--wg-s1) 0; padding: 0; color: var(--wg-text); }}
.wg-item-name {{ font-weight: 650; font-size: 1.02rem; line-height: 1.3; }}
.wg-item-meta {{ color: var(--wg-muted); font-size: 0.84rem; line-height: 1.45; }}
.wg-dot {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%;
  margin-right: 0.4rem; vertical-align: 0.06rem; background: currentColor; }}
.wg-verdict {{ border-left: 3px solid var(--wg-gold); padding: 2px 0 2px var(--wg-s4); }}
.wg-verdict.wg-neutral {{ border-left-color: var(--wg-border-strong); }}
.wg-verdict .wg-winner {{ font-size: 1.45rem; font-weight: 700; letter-spacing: -0.01em;
  line-height: 1.25; margin-top: 6px; }}
.wg-verdict .wg-sub {{ color: var(--wg-muted); margin-top: 2px; font-size: 0.92rem; }}

/* ---- Metric tiles ----------------------------------------------------------------------- */
.wg-tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--wg-s3); margin: var(--wg-s4) 0 var(--wg-s2) 0; }}
.wg-tile {{ border: 1px solid var(--wg-border); border-radius: 10px;
  padding: var(--wg-s3) var(--wg-s4); background: var(--wg-surface); min-width: 0;
  container-type: inline-size; }}
.wg-tile.wg-picked {{ border-color: var(--wg-gold); box-shadow: inset 0 0 0 1px var(--wg-gold); }}
.wg-tile .wg-tile-label {{ color: var(--wg-muted); font-size: 0.78rem; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
/* A value scales with its tile, so a number is never cut short; the unit wraps under it
   first. (1.45rem is for a browser without container queries.) */
.wg-tile .wg-tile-value {{ font-size: 1.45rem; font-size: clamp(1.1rem, 18cqi, 1.55rem);
  font-weight: 650; line-height: 1.25; font-variant-numeric: tabular-nums; margin-top: 2px;
  display: flex; flex-wrap: wrap; align-items: baseline; column-gap: 0.25rem; }}
.wg-tile .wg-tile-number {{ white-space: nowrap; }}
.wg-tile .wg-tile-value.wg-text-value {{ display: block; font-size: 1.05rem; font-weight: 600;
  padding-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.wg-tile .wg-tile-unit {{ color: var(--wg-muted); font-size: 0.8rem; font-weight: 500; }}
.wg-tile .wg-tile-context {{ color: var(--wg-muted); font-size: 0.8rem; margin-top: 2px; }}
.wg-delta-good {{ color: var(--wg-good); }}
.wg-delta-bad {{ color: var(--wg-bad); }}

/* ---- Explanations, notes, empty states ---------------------------------------------------- */
.wg-why {{ list-style: none; padding: 0; margin: var(--wg-s1) 0 0 0; }}
.wg-why li {{ display: grid; grid-template-columns: 6.2rem 1fr; gap: var(--wg-s3);
  align-items: baseline; padding: 7px 0; border-bottom: 1px solid var(--wg-border); }}
.wg-why li:last-child {{ border-bottom: none; }}
.wg-why .wg-amount {{ font-variant-numeric: tabular-nums; font-weight: 650; text-align: right;
  white-space: nowrap; }}
.wg-why .wg-note {{ color: var(--wg-muted); font-size: 0.84rem; }}
.wg-notes {{ list-style: none; margin: 0; padding: var(--wg-s3) var(--wg-s4);
  background: var(--wg-surface-alt); border: 1px solid var(--wg-border);
  border-radius: var(--wg-radius-sm); }}
.wg-notes li {{ display: flex; gap: var(--wg-s2); font-size: 0.875rem; line-height: 1.45;
  color: var(--wg-text-2); padding: 3px 0; }}
.wg-notes li::before {{ content: ""; flex: 0 0 6px; height: 6px; margin-top: 0.5em;
  border-radius: 50%; background: var(--wg-navy); }}
.wg-notes li.wg-warn::before {{ background: var(--wg-warning); }}
.wg-notes li.wg-problem::before {{ background: var(--wg-bad); }}
.wg-empty {{ border: 1px dashed var(--wg-border-strong); border-radius: var(--wg-radius);
  padding: var(--wg-s5); color: var(--wg-muted); display: flex; gap: var(--wg-s4);
  align-items: flex-start; }}
.wg-empty-icon {{ flex: 0 0 auto; width: 32px; height: 32px; border-radius: 8px;
  background: var(--wg-gold-soft); color: var(--wg-gold); display: flex;
  align-items: center; justify-content: center; }}
.wg-empty-icon img {{ width: 18px; height: 18px; display: block; }}
.wg-empty-title {{ color: var(--wg-text); font-weight: 650; font-size: 0.98rem;
  margin-bottom: 2px; }}
.wg-empty-body {{ font-size: 0.9rem; line-height: 1.5; }}
.wg-empty ol {{ margin: var(--wg-s2) 0 0 1.1rem; padding: 0; font-size: 0.9rem; }}
.wg-empty b {{ color: var(--wg-text); }}
.wg-small {{ color: var(--wg-muted); font-size: 0.84rem; line-height: 1.5; }}
.wg-assume {{ color: var(--wg-gold); font-weight: 600; font-size: 0.86rem; }}
.wg-list {{ margin: var(--wg-s1) 0 var(--wg-s2) 1.1rem; padding: 0; }}
.wg-list li {{ margin: 3px 0; line-height: 1.45; }}

/* ---- Tables ------------------------------------------------------------------------------ */
.wg-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; margin: var(--wg-s1) 0; }}
.wg-table th {{ text-align: left; color: var(--wg-muted); font-weight: 650; font-size: 0.72rem;
  text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap;
  border-bottom: 1px solid var(--wg-border-strong); padding: var(--wg-s2) var(--wg-s3); }}
.wg-table td {{ border-bottom: 1px solid var(--wg-border); padding: 9px var(--wg-s3);
  vertical-align: top; line-height: 1.45; }}
.wg-table tbody tr:last-child td {{ border-bottom: none; }}
.wg-table tbody tr:hover td {{ background: var(--wg-row-hover); }}
.wg-table .wg-num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.wg-table .wg-nowrap {{ white-space: nowrap; }}
.wg-table .wg-label {{ color: var(--wg-muted); white-space: nowrap; width: 1%; }}

/* ---- Gear slots, caps -------------------------------------------------------------------- */
[class*="st-key-wg-slot-"] {{ border-top: 1px solid var(--wg-border); padding-top: var(--wg-s2); }}
[class*="st-key-wg-slot-first"] {{ border-top: none; padding-top: 0; }}
.wg-slot {{ min-width: 0; }}
.wg-slot-top {{ display: flex; justify-content: space-between; align-items: center;
  gap: 0.4rem; min-height: 1.4rem; }}
.wg-slot-top .wg-eyebrow {{ margin-bottom: 0; }}
.wg-slot-top .wg-chip {{ font-size: 0.74rem; padding: 0 8px; }}
.wg-slot-name {{ font-weight: 600; line-height: 1.3; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }}
.wg-slot-none {{ color: var(--wg-muted); font-weight: 400; font-style: italic; }}
.wg-slot-meta {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.wg-bar {{ height: 6px; border-radius: 999px; background: var(--wg-neutral-soft);
  overflow: hidden; margin: 6px 0 4px 0; }}
.wg-bar > span {{ display: block; height: 100%; border-radius: inherit;
  background: var(--wg-gold); }}
.wg-bar.wg-good > span {{ background: var(--wg-good); }}
.wg-bar.wg-bad > span {{ background: var(--wg-bad); }}
.wg-cap {{ padding: 10px 0; border-bottom: 1px solid var(--wg-border); }}
.wg-cap:last-child {{ border-bottom: none; }}
.wg-cap-head {{ display: flex; justify-content: space-between; align-items: baseline;
  gap: 0.5rem; flex-wrap: wrap; }}

/* ---- Tablets and small laptops ------------------------------------------------------ */
/* Streamlit stacks columns only below 640px. A page's side-by-side columns stack below a
   tablet's width; the gear page's, which need more room, below a laptop's. */
@media (max-width: 1279px) {{
  [class*="st-key-wg-split-laptop-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] {{ row-gap: var(--wg-s4) !important; }}
  [class*="st-key-wg-split-laptop-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 100% !important; }}
}}
@media (max-width: 959px) {{
  [class*="st-key-wg-split-tablet-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] {{ row-gap: var(--wg-s4) !important; }}
  [class*="st-key-wg-split-tablet-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 100% !important; }}
}}
/* The rows of choices at the top of a page wrap as a grid, so no choice is cut short. */
@media (min-width: 641px) and (max-width: 1279px) {{
  .st-key-wg-card-context > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
  .st-key-wg-card-details > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{
    display: grid !important; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--wg-s3) var(--wg-s4) !important; }}
  .st-key-wg-card-context > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"],
  .st-key-wg-card-details > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"] {{ width: auto !important; min-width: 0 !important; }}
  /* The build profile's name is long: it takes two cells. */
  .st-key-wg-card-details > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"]:nth-child(2) {{ grid-column: span 2; }}
}}

/* ---- Narrow screens ---------------------------------------------------------------------- */
@media (max-width: 640px) {{
  /* Stacked columns sit as close as the page's other blocks. */
  [data-testid="stHorizontalBlock"] {{ row-gap: var(--wg-s4) !important; }}
  /* A slot's row, and a chosen item's, keeps its button beside it. */
  [class*="st-key-wg-slot-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; }}
  [class*="st-key-wg-slot-"] > [data-testid="stLayoutWrapper"]
    > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 0 !important; }}
  .wg-page-title {{ font-size: 1.45rem; }}
  .wg-page-icon {{ display: none; }}
  .wg-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  /* A wide table scrolls inside itself; columns keep a readable width. */
  .wg-table {{ display: block; overflow-x: auto; }}
  .wg-table th, .wg-table td {{ min-width: 6.5rem; overflow-wrap: break-word; }}
  .wg-table .wg-num {{ min-width: 3.5rem; }}
  .wg-table td:last-child:not(.wg-num) {{ min-width: 15rem; }}
}}
{quality}
</style>
"""


def inject() -> Tokens:
    """Add the stylesheet to the page and return the tokens in use."""
    t = tokens()
    st.html(_css(t))
    return t
