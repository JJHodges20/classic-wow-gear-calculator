"""The ``wowgear`` command line. It calls services; it computes nothing itself."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from wow_gear import __version__
from wow_gear.core import ConfigError, Settings, configure_logging, load_settings
from wow_gear.core.errors import DataValidationError, NotFoundError
from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.enums import EquipmentSlot, Stat
from wow_gear.models.gear import ReplacementResult, SavedCharacter
from wow_gear.reporting.export import (
    analysis_json,
    comparison_csv,
    comparison_html,
    comparison_json,
    components_csv,
)
from wow_gear.reporting.text import comparison_text, gear_text
from wow_gear.services.characters import parse_slot
from wow_gear.services.workspace import Workspace

app = typer.Typer(
    help="Classic Gear Calculator: explainable gear comparisons for WoW Classic.",
    no_args_is_help=True,
    add_completion=False,
)
items_app = typer.Typer(help="Find and import items.", no_args_is_help=True)
app.add_typer(items_app, name="items")

APP_SCRIPT = Path("apps") / "streamlit_app" / "app.py"
_STATUS_MARK = {"ok": "ok  ", "info": "info", "warning": "WARN", "error": "FAIL"}


def _version(show: bool) -> None:
    if show:
        typer.echo(f"wowgear {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", help="Print the version and exit.", callback=_version, is_eager=True
    ),
) -> None:
    """Classic Gear Calculator."""


def _settings() -> Settings:
    try:
        settings = load_settings()
    except ConfigError as error:
        typer.echo(f"Configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error
    configure_logging(
        settings.log_level,
        secrets=[value for name, value in settings.environment.items() if "SECRET" in name],
    )
    return settings


def _workspace() -> Workspace:
    settings = _settings()
    try:
        return Workspace(settings)
    except ConfigError as error:
        typer.echo(f"Configuration error: {error}", err=True)
        raise typer.Exit(code=2) from error


@app.command()
def check() -> None:
    """Validate the configuration, load the data, and report what each provider can do."""
    workspace = _workspace()
    failed = False
    try:
        for item in workspace.health.checks():
            typer.echo(f"[{_STATUS_MARK[item.status]}] {item.name}: {item.detail}")
            failed = failed or item.status == "error"
    finally:
        workspace.close()
    raise typer.Exit(code=1 if failed else 0)


@items_app.command("search")
def items_search(
    text: Annotated[str, typer.Argument(help="Part of an item name, or an item id.")],
    online: bool = typer.Option(False, "--online", help="Also ask the online provider."),
    limit: int = typer.Option(10, help="Show at most this many items."),
) -> None:
    """Search items by name or id."""
    workspace = _workspace()
    try:
        outcome = workspace.search.search(text, limit=limit, online=online)
        for notice in outcome.notices:
            typer.echo(f"note: {notice}")
        if not outcome.hits:
            typer.echo("No items found.")
        for hit in outcome.hits:
            item = hit.item
            kind = item.armor_type or item.weapon_type or item.relic_type or ""
            stats = ", ".join(f"{value:g} {stat.value}" for stat, value in item.stats.items())
            typer.echo(f"{item.id:<20} {item.name} [{item.slot} {kind}] ({hit.origin}) {stats}")
    finally:
        workspace.close()


@items_app.command("import")
def items_import(
    path: Annotated[Path, typer.Argument(help="A .csv or .json file of items.")],
) -> None:
    """Import items from a file; they are kept as your own items."""
    workspace = _workspace()
    try:
        report = workspace.search.import_file(path)
    except Exception as error:  # a bad file is reported, not a crash
        typer.echo(f"Import failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    finally:
        workspace.close()
    typer.echo(f"Imported {len(report.imported)} item(s); rejected {len(report.rejected)}.")
    for record in report.rejected:
        typer.echo(f"  row {record.row}: {'; '.join(record.errors)}")
    raise typer.Exit(code=0 if report.imported or not report.rejected else 1)


def _resolve(workspace: Workspace, reference: str) -> str:
    """An item id from an id or an exact name; a vague name is an error listing candidates."""
    hits = workspace.search.search(reference, limit=10).hits
    wanted = reference.strip().lower()
    exact = {hit.item.id for hit in hits if wanted in (hit.item.id.lower(), hit.item.name.lower())}
    if len(exact) == 1:
        return exact.pop()
    if len(hits) == 1:
        return hits[0].item.id
    if not hits:
        raise NotFoundError(f"no item matches {reference!r}")
    names = "; ".join(f"{hit.item.name} ({hit.item.id})" for hit in hits[:5])
    raise NotFoundError(f"{reference!r} matches several items: {names}")


def _gear_totals(values: list[str]) -> dict[str, float] | None:
    if not values:
        return None
    totals: dict[str, float] = {}
    known = {stat.value for stat in Stat}
    for value in values:
        stat, separator, number = (part.strip() for part in value.partition("="))
        try:
            amount = float(number)
        except ValueError:
            separator = ""
        if not separator:
            raise DataValidationError(f"--current takes STAT=NUMBER, such as hit=5; got {value!r}")
        if stat not in known:
            raise DataValidationError(
                f"--current: {stat!r} is not a stat; use names such as hit, crit, spell_hit, "
                "defense or strength"
            )
        totals[stat] = amount
    return totals


@app.command()
def compare(
    items: Annotated[list[str], typer.Argument(help="Item ids or exact names (one or more).")],
    profile: Annotated[str, typer.Option("--profile", "-p", help="Build profile id.")],
    phase: Annotated[
        int | None, typer.Option(help="Content phase (default: the profile's).")
    ] = None,
    level: Annotated[
        int | None, typer.Option(help="Character level (default: the profile's).")
    ] = None,
    race: Annotated[str | None, typer.Option(help="Race, for racial weapon skill.")] = None,
    content: Annotated[str | None, typer.Option(help="Content mode, such as raid_pve.")] = None,
    current: Annotated[
        list[str] | None,
        typer.Option(help="A gear total from your other items, STAT=NUMBER; repeat it."),
    ] = None,
    replacing: Annotated[
        str | None, typer.Option(help="The equipped item the candidates would replace.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the full result as JSON.")] = False,
    output: Annotated[
        Path | None,
        typer.Option(help="Also write the result to a .json, .csv, .html or .txt file."),
    ] = None,
    components: Annotated[
        Path | None, typer.Option(help="Also write every score component to a CSV file.")
    ] = None,
) -> None:
    """Compare items for a build profile and explain the difference."""
    if output is not None and output.suffix.lower() not in COMPARISON_FILES:
        typer.echo("--output takes a .json, .csv, .html or .txt file", err=True)
        raise typer.Exit(code=2)
    workspace = _workspace()
    try:
        calculator = workspace.calculator
        context = calculator.context(
            profile,
            phase=phase,
            level=level,
            race=race,
            content_mode=content,
            current_stats=_gear_totals(current or []),
        )
        ids = [_resolve(workspace, reference) for reference in items]
        replaced = _resolve(workspace, replacing) if replacing else None
        result = calculator.compare_ids(ids, context, replacing_id=replaced)
    except (DataValidationError, NotFoundError) as error:
        typer.echo(f"Cannot compare: {error}", err=True)
        raise typer.Exit(code=2) from error
    finally:
        workspace.close()
    typer.echo(result.model_dump_json(indent=2) if as_json else comparison_text(result))
    if output is not None:
        _write(output, _comparison_file(result, context, output.suffix.lower()))
    if components is not None:
        _write(components, components_csv(result))


COMPARISON_FILES = (".json", ".csv", ".html", ".txt")


def _comparison_file(result: ComparisonResult, context: CharacterContext, suffix: str) -> str:
    if suffix == ".json":
        return comparison_json(result)
    if suffix == ".csv":
        return comparison_csv(result)
    if suffix == ".html":
        return comparison_html(result, context)
    return comparison_text(result) + chr(10)


def _write(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        typer.echo(f"Cannot write {path}: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Wrote {path}")


def _character(workspace: Workspace, reference: str) -> SavedCharacter:
    """A saved character by id, or a character file exported from the app."""
    path = Path(reference)
    if path.suffix.lower() == ".json" and path.is_file():
        return workspace.characters.import_text(path.read_text(encoding="utf-8-sig"), ".json")
    return workspace.characters.get(reference)


@app.command()
def gear(
    character: Annotated[
        str | None,
        typer.Argument(help="A saved character's id, or a character .json file from the app."),
    ] = None,
    trying: Annotated[
        str | None,
        typer.Option("--try", help="Try an item in a slot, SLOT=ITEM, such as main_hand=12784."),
    ] = None,
    output: Annotated[
        Path | None, typer.Option(help="Also write the analysis to a .json or .html file.")
    ] = None,
) -> None:
    """Analyse a character's whole gear, or list the saved characters."""
    workspace = _workspace()
    try:
        service = workspace.characters
        if character is None:
            saved = service.all()
            if not saved:
                typer.echo("No saved characters. Save one on the Gear set page of the app.")
            for entry in saved:
                typer.echo(
                    f"{entry.id:<24} {entry.name} (level {entry.level} {entry.class_name.value}, "
                    f"{entry.profile_id}, {len(entry.gear.items)} pieces)"
                )
            return
        chosen = _character(workspace, character)
        analysis, _ = service.analyse(chosen)
        tried: ReplacementResult | None = None
        if trying is not None:
            slot_text, separator, item_text = (part.strip() for part in trying.partition("="))
            if not separator or not item_text:
                raise DataValidationError(f"--try takes SLOT=ITEM; got {trying!r}")
            slot: EquipmentSlot = parse_slot(slot_text)
            tried = service.try_replacement(chosen, slot, _resolve(workspace, item_text))
        if output is not None:
            suffix = output.suffix.lower()
            if suffix == ".json":
                _write(output, analysis_json(analysis))
            elif suffix == ".html":
                _write(output, service.export_html(chosen, analysis, tried))
            else:
                raise DataValidationError("--output takes a .json or .html file")
    except (DataValidationError, NotFoundError) as error:
        typer.echo(f"Cannot analyse: {error}", err=True)
        raise typer.Exit(code=2) from error
    finally:
        workspace.close()
    typer.echo(gear_text(chosen, analysis, tried))


@app.command()
def ui(
    port: int = typer.Option(8501, help="Port to serve the app on."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open a browser."),
) -> None:
    """Start the Streamlit app."""
    settings = _settings()
    # The app and its theme (.streamlit/) sit beside the package; WOWGEAR_HOME may name a
    # separate folder that holds only configuration and data.
    source = Path(__file__).resolve().parents[2]
    home = source if (source / APP_SCRIPT).is_file() else Path(settings.root)
    script = home / APP_SCRIPT
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script),
        "--server.port",
        str(port),
        "--server.headless",
        "true" if no_browser else "false",
        # A local tool: Streamlit's usage statistics would otherwise be sent to Streamlit.
        "--browser.gatherUsageStats",
        "false",
    ]
    raise typer.Exit(code=subprocess.call(command, cwd=home))


def main() -> None:
    """Console entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    app()


if __name__ == "__main__":
    main()
