# 0006 - The app's structure and design system

Date: 2026-10-07. Status: accepted.

## Context

The roadmap asks for a polished calculator first and a theorycrafting lab second: a light
neutral page with navy and charcoal surfaces and warm gold accents, green only for
beneficial and red only for harmful differences, gold for what is selected or recommended,
never colour alone, a large result before the detail, compact stat chips, responsive layout,
and loading, empty, stale, provider-error and invalid-item states designed on purpose. The
app may import only models, services and reporting.

## Decision

1. **Streamlit's own theme carries the palette.** `.streamlit/config.toml` defines
   `[theme.light]` and `[theme.dark]` (Streamlit 1.65 supports both), so every widget
   follows; gold is the primary colour, so selected tabs, toggles and the primary button are
   gold. Fonts are Streamlit's bundled ones (sans-serif text, serif headings): nothing is
   fetched from a font service.
2. **Custom elements are small escaped HTML** (`components/html.py`, `components/items.py`):
   cards, chips, score tiles and the "why" list, styled by CSS variables that
   `components/theme.py` sets for the theme the browser reports. Every value from data is
   escaped - item names and effect texts come from files and imports.
3. **Signals never rely on colour alone**: differences carry ▲ or ▼ and a sign, the
   recommendation carries a "Recommended under this profile" label as well as its gold edge,
   and quality colour appears only as a small dot beside the item name.
4. **Structure**: `app.py` is the shell (page setup, theme, navigation at the top, footer);
   each page is a small script in `pages/` that draws a function from `views/` (so pages can
   be tested); `components/` draw; `state/` holds the session keys and
   the workspace, cached once per project (`WOWGEAR_HOME`) and shared by sessions.
5. **Errors stay services' errors**: `wow_gear.services.errors` re-exports the core errors so
   the app can catch them without importing `core`.
6. **A local tool stays local**: no Deploy button (`toolbarMode = "minimal"`) and no usage
   statistics (`gatherUsageStats = false`, also passed by `wowgear ui`).
7. **The app is type-checked** with the package (`mypy` strict over both).

## Consequences

- A page is a script in `pages/` registered in `app.py`, drawing a view built from the same
  components (milestone 8 moved pages from functions to scripts, which `streamlit.testing`
  can switch between).
- App tests run under `streamlit.testing` on a throwaway project with the fixture dataset;
  a browser check in light, dark and phone widths closes each UI milestone.

## Revision - 2026-10-07: the UI polish

After version 1, a design review found the pages hard to tell apart and noisy. The app
title repeated in a large serif font on every page, and no page had its own title. Cards
were used for every slot. Routine notes appeared as coloured alerts. Links used the default
blue. Spacing was ad hoc, and the layout broke between the phone and the wide screen.
Nothing about what the app does changed; the presentation did:

1. **Type**: sans-serif throughout (headings included) on a 15px base, a fixed heading
   scale, and tabular figures for numbers. Point 1's serif headings are withdrawn.
2. **Tokens**: `components/theme.py` holds one set of colour tokens per theme. The light
   theme is a warm paper page (`#F6F4EF`) with white surfaces; the dark theme is slate
   (`#0E131B`). There is one gold accent (selected, recommended, the primary action) and
   navy for links and information. A spacing scale of 4/8/12/16/24/32/48px and two radii
   complete the set. `.streamlit/config.toml` carries the same colours for Streamlit's own
   widgets.
3. **Components**: `components/layout.py` draws every page the same way: the logo in the
   top bar, a page header (icon, title, one sentence), section headers with a count beside
   them, and a card for each logical panel (Streamlit's bordered containers with a
   `wg-card-*` key, which the CSS targets). It also draws an inset for an editor under a row,
   metric tiles, quiet notes (a dot and a sentence), empty states that say what to do, and
   the footer.
4. **Alerts only for problems**: a warning or an error is still an alert. A note that
   explains a result is a list item.
5. **Contrast and focus**: text meets 4.5:1 in both themes. A gold button's label is dark in
   the dark theme, where white on the brighter gold read at 2.3:1. Links and the top
   navigation show a gold outline when the keyboard reaches them.
6. **Responsive**: Streamlit stacks columns only below 640px, so `layout.split` wraps a
   page's columns in a keyed container that the CSS stacks below 960px (below 1280px on the
   gear page, whose two slot panels need the room). The rows of choices at the top of a page
   wrap as a grid on tablets. A tile's number scales with the tile (a container query)
   instead of being cut short. On a phone, a slot's row keeps its button beside it.

The CSS relies on Streamlit's `data-testid` names (`stHorizontalBlock`, `stColumn`,
`stLayoutWrapper`) and on the `st-key-*` class a keyed container gets. If a Streamlit upgrade
renames them, the pages fall back to Streamlit's own layout rather than break. Check the
pages in a browser after an upgrade.
