"""Shared test fixtures. No test writes under data/, reads the user's data or uses the network."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLED = PROJECT_ROOT / "data" / "fixtures" / "bundled"


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A throwaway project root: a copy of configs/ with its own empty data directory."""
    root = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT / "configs", root / "configs")
    (root / "data").mkdir()
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project root using the fixture dataset and its own empty data directory."""
    root = tmp_path / "project"
    shutil.copytree(PROJECT_ROOT / "configs", root / "configs")
    app = root / "configs" / "app.yaml"
    text = app.read_text(encoding="utf-8").replace(
        "bundled_dir: data/bundled", f"bundled_dir: {BUNDLED.as_posix()}"
    )
    app.write_text(text, encoding="utf-8")
    return root
