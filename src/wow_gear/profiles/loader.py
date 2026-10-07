"""Loading build profiles from ``configs/profiles/<class>/<id>.yaml`` and checking them
against their ruleset.

A profile that names a conversion, a cap formula, a stat or a role its ruleset does not have
is rejected at load time with the file and the reason, so a broken profile never reaches the
scoring engine.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError

from wow_gear.core.errors import ConfigError, NotFoundError
from wow_gear.models.enums import WEAPON_DPS_STATS, ClassName, Role, Stat
from wow_gear.models.profile import BuildProfile, CapReference
from wow_gear.models.ruleset import Ruleset
from wow_gear.rulesets.loader import RulesetRegistry


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error


def profile_problems(profile: BuildProfile, ruleset: Ruleset) -> list[str]:
    """Everything in ``profile`` that its ruleset does not support. Empty means valid."""
    problems: list[str] = []
    if profile.ruleset != ruleset.id:
        problems.append(f"targets ruleset {profile.ruleset!r}, checked against {ruleset.id!r}")
        return problems
    class_names = {class_def.name for class_def in ruleset.classes}
    if profile.class_name not in class_names:
        problems.append(f"class {profile.class_name} is not in the ruleset")
        return problems
    class_def = ruleset.class_def(profile.class_name)
    if profile.role not in class_def.roles:
        problems.append(f"{profile.class_name} has no {profile.role} role in the ruleset")
    if not ruleset.min_level <= profile.target_level <= ruleset.max_level:
        problems.append(f"target level {profile.target_level} is outside the ruleset's levels")
    phases = {phase.number for phase in ruleset.phases}
    if profile.target_phase is not None and profile.target_phase not in phases:
        problems.append(f"target phase {profile.target_phase} is not a ruleset phase")
    for weight in profile.stat_weights:
        if weight.stat not in WEAPON_DPS_STATS and not ruleset.allows(weight.stat):
            problems.append(f"weights {weight.stat}, which the ruleset does not allow")
    for rule in profile.derived_stats:
        if ruleset.conversion(profile.class_name, rule.conversion) is None:
            problems.append(
                f"derives {rule.conversion}, a conversion the ruleset has no value for "
                f"{profile.class_name}"
            )
    references: list[tuple[Stat, CapReference]] = [
        *((cap.stat, cap.cap) for cap in profile.hard_caps),
        *((cap.stat, cap.starts_at) for cap in profile.soft_caps),
        *((cap.stat, cap.ends_at) for cap in profile.soft_caps if cap.ends_at is not None),
        *((threshold.stat, threshold.at) for threshold in profile.thresholds),
    ]
    for stat, reference in references:
        if reference.ruleset_cap is None:
            continue
        cap = ruleset.caps.get(reference.ruleset_cap)
        if cap is None:
            problems.append(f"refers to cap {reference.ruleset_cap!r}, not in the ruleset")
        elif cap.stat != stat:
            problems.append(
                f"applies cap {reference.ruleset_cap!r} (a cap on {cap.stat}) to {stat}"
            )
    return problems


def load_profile(path: Path, rulesets: RulesetRegistry) -> BuildProfile:
    """Read one profile file and check it against its ruleset."""
    try:
        profile = BuildProfile.model_validate(_read_yaml(path))
    except ValidationError as error:
        raise ConfigError(f"{path} is not a valid build profile:\n{error}") from error
    if profile.id != path.stem:
        raise ConfigError(f"{path}: profile id {profile.id!r} must match the file name")
    if path.parent.name != profile.class_name:
        raise ConfigError(
            f"{path}: a {profile.class_name} profile belongs in a folder of that name"
        )
    try:
        ruleset = rulesets.get(profile.ruleset)
    except NotFoundError as error:
        raise ConfigError(f"{path}: {error}") from error
    problems = profile_problems(profile, ruleset)
    if problems:
        raise ConfigError(f"{path}: " + "; ".join(problems))
    return profile


class ProfileRegistry:
    """Every build profile, by id, with lookups by class and role."""

    def __init__(self, profiles: Iterable[BuildProfile]) -> None:
        by_id: dict[str, BuildProfile] = {}
        for profile in profiles:
            if profile.id in by_id:
                raise ConfigError(f"two profiles share the id {profile.id!r}")
            by_id[profile.id] = profile
        self._profiles = dict(sorted(by_id.items()))

    @classmethod
    def from_directory(cls, directory: Path, rulesets: RulesetRegistry) -> ProfileRegistry:
        paths = sorted(directory.glob("*/*.yaml"))
        return cls(load_profile(path, rulesets) for path in paths)

    def get(self, profile_id: str) -> BuildProfile:
        try:
            return self._profiles[profile_id]
        except KeyError:
            raise NotFoundError(f"no build profile {profile_id!r}") from None

    def for_ruleset(self, ruleset_id: str) -> list[BuildProfile]:
        return [p for p in self._profiles.values() if p.ruleset == ruleset_id]

    def classes(self, ruleset_id: str) -> list[ClassName]:
        present = {p.class_name for p in self.for_ruleset(ruleset_id)}
        return [class_name for class_name in ClassName if class_name in present]

    def roles(self, ruleset_id: str, class_name: ClassName) -> list[Role]:
        present = {p.role for p in self.for_ruleset(ruleset_id) if p.class_name == class_name}
        return [role for role in Role if role in present]

    def profiles(self, ruleset_id: str, class_name: ClassName, role: Role) -> list[BuildProfile]:
        return [
            p for p in self.for_ruleset(ruleset_id) if p.class_name == class_name and p.role == role
        ]

    def __iter__(self) -> Iterator[BuildProfile]:
        return iter(self._profiles.values())

    def __len__(self) -> int:
        return len(self._profiles)
