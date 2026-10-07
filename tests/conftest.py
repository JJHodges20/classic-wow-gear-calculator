"""Shared test fixtures. No test writes under data/, reads the user's data or uses the network."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
