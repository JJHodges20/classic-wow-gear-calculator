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
   pages are functions in `pages/`; `components/` draw; `state/` holds the session keys and
   the workspace, cached once per project (`WOWGEAR_HOME`) and shared by sessions.
5. **Errors stay services' errors**: `wow_gear.services.errors` re-exports the core errors so
   the app can catch them without importing `core`.
6. **A local tool stays local**: no Deploy button (`toolbarMode = "minimal"`) and no usage
   statistics (`gatherUsageStats = false`, also passed by `wowgear ui`).
7. **The app is type-checked** with the package (`mypy` strict over both).

## Consequences

- A page added in milestone 8 is a function registered in `app.py` and built from the same
  components; the navigation appears once there is more than one page.
- App tests run under `streamlit.testing` on a throwaway project with the fixture dataset;
  a browser check in light, dark and phone widths closes each UI milestone.
