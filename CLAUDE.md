# Classic Gear Calculator - Engineering Rules

A local-first Python app that compares World of Warcraft Classic items for a chosen ruleset,
class, role and build profile, and explains why one item is better. Built from the roadmap in
`docs/roadmap/` in bounded milestones, each closed by a gate (see "Definition of done").

Read before changing anything: this file, `docs/ROADMAP.md` (milestone status),
`docs/ARCHITECTURE.md`, the top entry of `docs/DEVELOPMENT_LOG.md`, then `git status`.

## Architecture

- Rulesets own version-specific game mechanics.
- Build profiles own class/role priorities and assumptions.
- Calculation modules own formulas.
- Scoring modules combine calculation outputs into comparisons.
- UI code never performs game math.
- Provider adapters never contain scoring logic.
- The UI and the command line call `wow_gear.services` only.

Layer imports are fixed and enforced by `tests/unit/test_architecture.py`:

| Layer | May import |
| --- | --- |
| core | nothing in wow_gear |
| models | core |
| rulesets | core, models |
| profiles | core, models, rulesets |
| processing | core, models, rulesets |
| data_sources | core, models |
| repositories | core, models |
| calculations | core, models, rulesets |
| scoring | core, models, rulesets, profiles, calculations |
| comparison | scoring and everything scoring may import |
| optimizer | comparison and everything comparison may import |
| reporting | core, models |
| services | every layer |
| cli (`wow_gear/cli.py`) | core, models, services, reporting |
| app (`apps/streamlit_app`) | models, services, reporting |

`httpx` belongs to data_sources, `sqlalchemy` to repositories, `streamlit` and `plotly` to the
app. Provider response schemas (`wow_gear.models.providers`) never reach rulesets, profiles,
calculations, scoring, comparison or the optimizer. A failing boundary test means the code is
in the wrong layer: move it, do not widen the rule.

## Data integrity

- Preserve provider IDs and source metadata.
- Normalize all items into the canonical Item model.
- Manual and looked-up items use the same validation/scoring path.
- Ruleset, profile, and item-data versions must be traceable.
- Secrets live in the environment or `.env`, never in `configs/` or code. `.env.example` lists
  every variable with an empty value.
- Wowhead is a human reference: link to it, never fetch or scrape it.

## Theorycraft correctness

- Never assume one stat weight applies to every class/role.
- Caps and breakpoints are context-dependent.
- Do not silently invent missing proc or set-bonus values.
- Expose assumptions and uncertainty to the user.
- Prefer testable formulas over opaque recommendation logic.
- Every game-mechanic value in `configs/` cites the source it was taken from. Nothing is added
  from memory. A value no source supports is an assumption, labelled as one, in a profile
  marked draft or experimental.

## Testing

- Every formula requires deterministic tests.
- Use hand-reviewed golden fixtures for critical comparisons.
- Do not modify expected values merely to make a failing test pass.
- Run the full suite before closing a milestone.
- Warnings are errors (`filterwarnings = error`); add a targeted ignore, with a reason, only
  for warnings raised inside third-party code.
- No test writes under `data/` or reads the user's data (`data/user`, `data/cache`,
  `data/raw`); tests read only the committed fixtures and, read-only, the bundled dataset. No
  test touches the network: tests that need it are marked `network` and deselected by default.
- Each shipped profile keeps at least five hand-reviewed comparisons in
  `data/fixtures/reviews/<profile id>/`, run by `tests/regression/test_profile_reviews.py`.

## Development

- Inspect existing code before edits.
- Implement the smallest coherent change.
- Avoid unrelated refactors during feature work.
- Update docs when rules, profiles, data sources, or user behavior change.

## Definition of done (every milestone)

Implementation complete, then: targeted tests pass, full suite passes, `ruff check`, `ruff
format --check` and `mypy` clean, no provider secrets in the repository, manual UI smoke test
in a real browser passes (light and dark), assumptions documented, git diff reviewed, a
development-log entry written, and the milestone committed locally. Never push; no remote
is configured.

## Commands

Run from the project root (Windows, PowerShell or Git Bash):

```
.\.venv\Scripts\python.exe -m pytest -n auto      # full suite
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe                          # strict, src/wow_gear
.\.venv\Scripts\wowgear.exe check                 # validate configuration
.\.venv\Scripts\wowgear.exe ui --no-browser --port 8601
```

Set up from scratch with `scripts\bootstrap.ps1`. The bundled item dataset is rebuilt from a
VMaNGOS snapshot with `scripts\build_bundled_dataset.py` (see `data/bundled/README.md`); raw
downloads live in `data/raw/`, which git ignores.

## Tool notes

- In the Bash tool, a command whose text contains an apostrophe can fail to parse: write
  files with the Write tool or a `<<"EOF"` heredoc and keep one-liners apostrophe-free.
- The Windows console is cp1252: anything that prints accented names reconfigures stdout to
  UTF-8 first (`wowgear` does).
- A browser check of the UI must not run beside a parallel test run; restart the Streamlit
  server after any code change before taking screenshots.
- Git Bash rewrites an argument that looks like a POSIX path for native programs: a lone `/`
  becomes `C:/Program Files/Git/`. Pass a URL path as `""` or prefix the command with
  `MSYS_NO_PATHCONV=1`.
