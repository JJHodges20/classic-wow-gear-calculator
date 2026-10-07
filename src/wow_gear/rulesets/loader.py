"""Loading rulesets from ``configs/rulesets/*.yaml``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError

from wow_gear.core.errors import ConfigError, NotFoundError
from wow_gear.models.ruleset import Ruleset


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"missing ruleset file {path}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error


def load_ruleset(path: Path) -> Ruleset:
    """Read and validate one ruleset file. Its id must match the file name."""
    raw = _read_yaml(path)
    try:
        ruleset = Ruleset.model_validate(raw)
    except ValidationError as error:
        raise ConfigError(f"{path} is not a valid ruleset:\n{error}") from error
    if ruleset.id != path.stem:
        raise ConfigError(f"{path}: ruleset id {ruleset.id!r} must match the file name")
    return ruleset


class RulesetRegistry:
    """Every ruleset in a directory, by id."""

    def __init__(self, rulesets: dict[str, Ruleset]) -> None:
        if not rulesets:
            raise ConfigError("no rulesets configured")
        self._rulesets = dict(sorted(rulesets.items()))

    @classmethod
    def from_directory(cls, directory: Path) -> RulesetRegistry:
        files = sorted(directory.glob("*.yaml"))
        rulesets = {}
        for path in files:
            ruleset = load_ruleset(path)
            rulesets[ruleset.id] = ruleset
        return cls(rulesets)

    def get(self, ruleset_id: str) -> Ruleset:
        try:
            return self._rulesets[ruleset_id]
        except KeyError:
            raise NotFoundError(f"no ruleset {ruleset_id!r}") from None

    def ids(self) -> list[str]:
        return list(self._rulesets)

    def __iter__(self) -> Iterator[Ruleset]:
        return iter(self._rulesets.values())

    def __len__(self) -> int:
        return len(self._rulesets)
