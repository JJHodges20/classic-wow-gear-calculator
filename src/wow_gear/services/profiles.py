"""Build profiles: inspect the shipped ones, and keep the player's own customised copies.

A custom profile starts as a copy of a profile with the player's weights. It is saved under
``data/user/profiles/<class>/<id>.yaml`` with a version that goes up with every save, and
every version is kept under ``data/user/profiles/history/<id>/`` so an earlier result can be
reproduced. Custom profiles are experimental, and a weight the player set is labelled an
assumption - the shipped profiles and their sources are never changed.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from wow_gear.calculations.caps import evaluate_cap
from wow_gear.core.errors import ConfigError, DataValidationError, NotFoundError
from wow_gear.core.logging import get_logger
from wow_gear.models.character import CharacterContext
from wow_gear.models.enums import ClassName, Stat, ValidationStatus
from wow_gear.models.profile import BuildProfile, CapReference, StatWeight, WeightBasis
from wow_gear.models.ruleset import Ruleset
from wow_gear.profiles.loader import ProfileRegistry, load_profile, profile_problems
from wow_gear.rulesets.loader import RulesetRegistry

LOG = get_logger(__name__)
CUSTOM_PREFIX = "custom_"
HISTORY = "history"
YOUR_WEIGHTS = "Weights whose basis is an assumption were set by you, not taken from a source."


@dataclass(frozen=True)
class CapLine:
    """A profile's cap, soft cap or breakpoint, evaluated for a context."""

    stat: Stat
    kind: str
    value: float
    detail: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _bump(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


class ProfileService:
    def __init__(
        self, profiles: ProfileRegistry, rulesets: RulesetRegistry, user_dir: Path
    ) -> None:
        self._profiles = profiles
        self._rulesets = rulesets
        self._directory = user_dir / "profiles"
        self.problems: list[str] = []
        """Custom profile files that could not be loaded, with the reason."""

    # --- loading ------------------------------------------------------------------------

    def load_custom(self) -> int:
        """Add the saved custom profiles to the registry; a broken file is reported, not fatal."""
        loaded = 0
        if not self._directory.is_dir():
            return 0
        for path in sorted(self._directory.glob("*/*.yaml")):
            if path.parent.name == HISTORY:
                continue
            try:
                profile = load_profile(path, self._rulesets)
            except ConfigError as error:
                self.problems.append(str(error))
                LOG.warning("custom profile skipped: %s", error)
                continue
            if not profile.id.startswith(CUSTOM_PREFIX):
                self.problems.append(f"{path}: a custom profile id must start with {CUSTOM_PREFIX}")
                continue
            self._profiles.put(profile)
            loaded += 1
        return loaded

    # --- reading ------------------------------------------------------------------------

    def all(self) -> list[BuildProfile]:
        order = {name: index for index, name in enumerate(ClassName)}
        return sorted(
            self._profiles,
            key=lambda p: (order[p.class_name], p.role.value, self.is_custom(p.id), p.label),
        )

    def get(self, profile_id: str) -> BuildProfile:
        return self._profiles.get(profile_id)

    @staticmethod
    def is_custom(profile_id: str) -> bool:
        return profile_id.startswith(CUSTOM_PREFIX)

    def ruleset_of(self, profile: BuildProfile) -> Ruleset:
        return self._rulesets.get(profile.ruleset)

    def default_context(self, profile: BuildProfile) -> CharacterContext:
        ruleset = self.ruleset_of(profile)
        return CharacterContext(
            ruleset=ruleset.id,
            phase=profile.target_phase or ruleset.default_phase,
            level=profile.target_level,
            class_name=profile.class_name,
            role=profile.role,
            profile_id=profile.id,
            content_mode=profile.default_content_mode,
        )

    def caps(self, profile_id: str, context: CharacterContext | None = None) -> list[CapLine]:
        """The profile's caps and breakpoints, as numbers for ``context`` (default: its own)."""
        profile = self.get(profile_id)
        ruleset = self.ruleset_of(profile)
        context = context or self.default_context(profile)

        def value(reference: CapReference) -> tuple[float, str]:
            if reference.fixed is not None:
                amount = max(0.0, reference.fixed - reference.reduced_by)
                return amount, f"fixed at {reference.fixed:g}"
            assert reference.ruleset_cap is not None
            evaluated = evaluate_cap(reference.ruleset_cap, ruleset, context, reference.reduced_by)
            return evaluated.cap, evaluated.derivation

        lines = []
        for hard in profile.hard_caps:
            amount, detail = value(hard.cap)
            lines.append(CapLine(hard.stat, "hard cap", amount, detail))
        for soft in profile.soft_caps:
            amount, detail = value(soft.starts_at)
            end = f"; counts {soft.multiplier:.0%} beyond"
            if soft.ends_at is not None:
                until, _ = value(soft.ends_at)
                end += f" until {until:g}"
            lines.append(CapLine(soft.stat, "soft cap", amount, detail + end))
        for threshold in profile.thresholds:
            amount, detail = value(threshold.at)
            lines.append(
                CapLine(
                    threshold.stat,
                    f"breakpoint: {threshold.label}",
                    amount,
                    f"{detail}; worth {threshold.bonus:g} once reached",
                )
            )
        return lines

    def history(self, profile_id: str) -> list[str]:
        """The saved versions of a custom profile, oldest first."""
        folder = self._directory / HISTORY / profile_id
        if not folder.is_dir():
            return []
        versions = [path.stem for path in folder.glob("*.yaml")]
        return sorted(versions, key=lambda v: tuple(int(part) for part in v.split(".")))

    # --- saving -------------------------------------------------------------------------

    def save_custom(
        self,
        base_id: str,
        label: str,
        weights: Mapping[Stat, float],
        *,
        summary: str | None = None,
    ) -> BuildProfile:
        """Save ``base_id`` with the player's ``weights`` as a custom profile.

        A custom base is updated in place with the next version; a shipped base gives a new
        custom profile named after ``label``. Stats left out of ``weights`` are no longer
        valued. Raises ``DataValidationError`` with the reason when the result is invalid.
        """
        base = self.get(base_id)
        label = " ".join(label.split())
        if not label:
            raise DataValidationError("a custom profile needs a name")
        if not _slug(label):
            raise DataValidationError("the name needs letters or digits")
        profile_id = base.id if self.is_custom(base.id) else f"{CUSTOM_PREFIX}{_slug(label)}"
        existing = self._existing(profile_id)
        if existing is not None and not self.is_custom(base.id) and existing.id != base.id:
            raise DataValidationError(
                f"a custom profile named {existing.label!r} exists; open it to change it"
            )
        version = _bump(existing.version) if existing is not None else "1.0.0"

        kept = {weight.stat: weight for weight in base.stat_weights}
        new_weights = []
        for stat, amount in weights.items():
            old = kept.get(stat)
            if old is not None and old.weight == amount:
                new_weights.append(old)
                continue
            note = (
                f"Set by you; {base.label} {base.version} has {old.weight:g}."
                if old is not None
                else "Added by you."
            )
            new_weights.append(
                StatWeight(stat=stat, weight=float(amount), basis=WeightBasis.ASSUMPTION, note=note)
            )
        data = base.model_dump(mode="python")
        data.update(
            id=profile_id,
            version=version,
            label=label,
            summary=summary or base.summary,
            stat_weights=tuple(new_weights),
            validation_status=ValidationStatus.EXPERIMENTAL,
        )
        if not self.is_custom(base.id):
            data["notes"] = f"Based on {base.id} {base.version}."
            data["assumptions"] = (*base.assumptions, YOUR_WEIGHTS)
        try:
            profile = BuildProfile.model_validate(data)
        except ValidationError as error:
            reasons = "; ".join(issue["msg"] for issue in error.errors())
            raise DataValidationError(f"the profile is not valid: {reasons}") from error
        problems = profile_problems(profile, self.ruleset_of(profile))
        if problems:
            raise DataValidationError("the profile is not valid: " + "; ".join(problems))
        self._write(profile)
        self._profiles.put(profile)
        return profile

    def delete_custom(self, profile_id: str) -> None:
        """Remove a custom profile (its saved versions stay in the history folder)."""
        if not self.is_custom(profile_id):
            raise DataValidationError("only custom profiles can be deleted")
        profile = self.get(profile_id)
        path = self._directory / profile.class_name.value / f"{profile_id}.yaml"
        path.unlink(missing_ok=True)
        self._profiles.remove(profile_id)

    def _existing(self, profile_id: str) -> BuildProfile | None:
        try:
            return self.get(profile_id)
        except NotFoundError:
            return None

    def _write(self, profile: BuildProfile) -> None:
        text = yaml.safe_dump(
            profile.model_dump(mode="json", exclude_defaults=True),
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )
        folder = self._directory / profile.class_name.value
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{profile.id}.yaml"
        path.write_text(text, encoding="utf-8")
        history = self._directory / HISTORY / profile.id
        history.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, history / f"{profile.version}.yaml")
