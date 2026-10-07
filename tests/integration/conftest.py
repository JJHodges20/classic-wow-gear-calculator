"""Workspaces on throwaway project roots, with the fixture dataset and a fake Blizzard API."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

from wow_gear.core import load_settings
from wow_gear.data_sources.blizzard import BlizzardClient
from wow_gear.services.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
BLIZZARD = ROOT / "data" / "fixtures" / "providers" / "blizzard"
BUNDLED = ROOT / "data" / "fixtures" / "bundled"


def blizzard_handler(fail: str | None = None) -> Callable[[httpx.Request], httpx.Response]:
    """A fake Battle.net: the token endpoint, items by id, and search by name."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth.battle.net":
            return httpx.Response(200, json=json.loads((BLIZZARD / "token.json").read_text()))
        if fail == "connect":
            raise httpx.ConnectError("network is unreachable", request=request)
        if fail == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if fail in ("500", "429"):
            return httpx.Response(int(fail))
        if fail == "garbage":
            return httpx.Response(200, text="<html>maintenance</html>")
        path = request.url.path
        if path.startswith("/data/wow/item/"):
            source = BLIZZARD / f"item_{path.rsplit('/', 1)[-1]}.json"
            if not source.is_file():
                return httpx.Response(404, json={"code": 404, "type": "BLZWEBAPI00000404"})
            return httpx.Response(200, json=json.loads(source.read_text()))
        if path == "/data/wow/search/item":
            name = request.url.params.get("name.en_US", "").lower()
            for keyword in ("lionheart", "girdle"):
                if keyword in name:
                    return httpx.Response(
                        200, json=json.loads((BLIZZARD / f"search_{keyword}.json").read_text())
                    )
            return httpx.Response(
                200, json={"page": 1, "pageSize": 0, "pageCount": 0, "results": []}
            )
        return httpx.Response(404)

    return handler


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project root using the fixture dataset and its own empty data directory."""
    root = tmp_path / "project"
    shutil.copytree(ROOT / "configs", root / "configs")
    app = root / "configs" / "app.yaml"
    text = app.read_text(encoding="utf-8").replace(
        "bundled_dir: data/bundled", f"bundled_dir: {BUNDLED.as_posix()}"
    )
    app.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def open_workspace(project: Path) -> Iterator[Callable[..., Workspace]]:
    """Open workspaces on the project; ``fail`` makes the fake Blizzard API misbehave."""
    opened: list[Workspace] = []

    def make(*, online: bool = False, fail: str | None = None) -> Workspace:
        settings = load_settings(project, environment={})
        client = None
        if online:
            client = BlizzardClient(
                "test-id", "test-secret", transport=httpx.MockTransport(blizzard_handler(fail))
            )
        workspace = Workspace(settings, online=client)
        opened.append(workspace)
        return workspace

    yield make
    for workspace in opened:
        workspace.close()
