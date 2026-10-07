"""The ``wowgear`` command line. It calls services; it computes nothing itself."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from wow_gear import __version__
from wow_gear.core import ConfigError, Settings, configure_logging, load_settings
from wow_gear.services.workspace import Workspace

app = typer.Typer(
    help="Classic Gear Calculator: explainable gear comparisons for WoW Classic.",
    no_args_is_help=True,
    add_completion=False,
)
items_app = typer.Typer(help="Find and import items.", no_args_is_help=True)
app.add_typer(items_app, name="items")

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


@app.command()
def ui(
    port: int = typer.Option(8501, help="Port to serve the app on."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open a browser."),
) -> None:
    """Start the Streamlit app."""
    settings = _settings()
    script = settings.root / "apps" / "streamlit_app" / "app.py"
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
    ]
    raise typer.Exit(code=subprocess.call(command, cwd=Path(settings.root)))


def main() -> None:
    """Console entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    app()


if __name__ == "__main__":
    main()
