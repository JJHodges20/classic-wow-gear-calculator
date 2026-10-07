"""No provider secrets in the repository, and every secret documented in .env.example."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".json",
    ".csv",
    ".cfg",
    ".ini",
    "",
}

# An assignment of a non-empty value to anything that looks like a credential.
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:[A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|API_KEY)[A-Z0-9_]*)\s*[:=]\s*['\"]?([A-Za-z0-9/+_\-]{12,})"
)


def _tracked_or_candidate_files() -> list[Path]:
    """Files git would commit: tracked plus untracked-but-not-ignored."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        candidates = [ROOT / line for line in listed]
    except (OSError, subprocess.CalledProcessError):
        candidates = [path for path in ROOT.rglob("*") if path.is_file()]
    return [
        path
        for path in candidates
        if path.is_file()
        and not SKIP_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.suffix in TEXT_SUFFIXES
    ]


def _provider_secrets() -> set[str]:
    providers = yaml.safe_load((ROOT / "configs" / "providers.yaml").read_text(encoding="utf-8"))
    return {name for provider in providers["providers"] for name in provider.get("secrets", [])}


def test_no_file_that_git_would_commit_holds_a_credential() -> None:
    offenders = []
    for path in _tracked_or_candidate_files():
        if path.name == ".env.example":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in SECRET_ASSIGNMENT.finditer(text):
            value = match.group(1)
            if not value.isupper() and "example" not in value.lower():
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)[:40]}")
    assert not offenders, offenders


def test_dotenv_is_ignored_by_git() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored and "!.env.example" in ignored


def test_every_provider_secret_is_documented_and_blank_in_the_example() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = dict(
        line.split("=", 1) for line in example.splitlines() if line and not line.startswith("#")
    )
    for name in _provider_secrets():
        assert name in documented, f"{name} is missing from .env.example"
        assert documented[name].strip() == "", f"{name} has a value in .env.example"
