"""The ``wowgear`` command line. It calls services; it computes nothing itself."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from wow_gear import __version__
from wow_gear.core import ConfigError, Settings, configure_logging, load_settings
from wow_gear.services.health import HealthService

app = typer.Typer(
    help="Classic Gear Calculator: explainable gear comparisons for WoW Classic.",
    no_args_is_help=True,
    add_completion=False,
)

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


@app.command()
def check() -> None:
    """Validate the configuration and report what each provider can do."""
    health = HealthService(_settings())
    failed = False
    for item in health.checks():
        typer.echo(f"[{_STATUS_MARK[item.status]}] {item.name}: {item.detail}")
        failed = failed or item.status == "error"
    raise typer.Exit(code=1 if failed else 0)


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
