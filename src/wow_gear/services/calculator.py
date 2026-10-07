"""The calculator (roadmap sections 5 and 6): choose a context, then score or compare items.

The UI and the command line call this service. It turns choices into a checked context,
makes every item - manual, imported or looked up - pass the same validation, and hands the
math to the scoring engine and the comparison layer. It holds no game math itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import ValidationError

from wow_gear.comparison.compare import compare_items
from wow_gear.core.errors import DataValidationError, NotFoundError
from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult
from wow_gear.models.enums import ClassName, Role
from wow_gear.models.item import Item
from wow_gear.models.labels import ROLE_LABELS
from wow_gear.models.profile import BuildProfile
from wow_gear.models.ruleset import Ruleset
from wow_gear.models.score import ScoreResult
from wow_gear.processing.validation import validate_item
from wow_gear.profiles.loader import ProfileRegistry
from wow_gear.rulesets.loader import RulesetRegistry
from wow_gear.scoring.engine import score_item


class ItemSource(Protocol):
    """Where the calculator finds items by id (the search service)."""

    def get(self, item_id: str) -> Item | None: ...


def _readable(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in issue['loc']) or 'context'}: {issue['msg']}"
        for issue in error.errors()
    )


class CalculatorService:
    def __init__(
        self,
        rulesets: RulesetRegistry,
        profiles: ProfileRegistry,
        items: ItemSource | None = None,
    ) -> None:
        self._rulesets = rulesets
        self._profiles = profiles
        self._items = items

    # --- choosing a context -------------------------------------------------------------

    def ruleset(self, ruleset_id: str) -> Ruleset:
        return self._rulesets.get(ruleset_id)

    def classes(self, ruleset_id: str) -> list[tuple[ClassName, str]]:
        """Classes that have at least one build profile, with their labels."""
        ruleset = self.ruleset(ruleset_id)
        return [
            (name, ruleset.class_def(name).label) for name in self._profiles.classes(ruleset_id)
        ]

    def roles(self, ruleset_id: str, class_name: ClassName) -> list[tuple[Role, str]]:
        return [(role, ROLE_LABELS[role]) for role in self._profiles.roles(ruleset_id, class_name)]

    def profiles(self, ruleset_id: str, class_name: ClassName, role: Role) -> list[BuildProfile]:
        return self._profiles.profiles(ruleset_id, class_name, role)

    def profile(self, profile_id: str) -> BuildProfile:
        return self._profiles.get(profile_id)

    def context(self, profile_id: str, **choices: Any) -> CharacterContext:
        """A checked context for ``profile_id``; unspecified choices take the profile's defaults.

        Defaults: the profile's level and content mode, its target phase or the ruleset's
        default phase. Raises ``DataValidationError`` with a readable reason when a choice is
        invalid or does not fit the profile and its ruleset.
        """
        profile = self.profile(profile_id)
        ruleset = self.ruleset(profile.ruleset)
        values: dict[str, Any] = {
            "ruleset": ruleset.id,
            "phase": profile.target_phase or ruleset.default_phase,
            "level": profile.target_level,
            "class_name": profile.class_name,
            "role": profile.role,
            "profile_id": profile.id,
            "content_mode": profile.default_content_mode,
        }
        values.update({key: value for key, value in choices.items() if value is not None})
        try:
            context = CharacterContext.model_validate(values)
        except ValidationError as error:
            raise DataValidationError(_readable(error)) from error
        self.check(context)
        return context

    def check(self, context: CharacterContext) -> None:
        """Reject a context its ruleset or profile cannot score."""
        ruleset = self.ruleset(context.ruleset)
        profile = self.profile(context.profile_id)
        problems: list[str] = []
        if profile.ruleset != ruleset.id:
            problems.append(f"the {profile.label} profile is for {profile.ruleset}")
        if (profile.class_name, profile.role) != (context.class_name, context.role):
            problems.append(
                f"the {profile.label} profile is for a {profile.class_name} "
                f"{ROLE_LABELS[profile.role].lower()}"
            )
        if not ruleset.min_level <= context.level <= ruleset.max_level:
            problems.append(
                f"level {context.level} is outside {ruleset.min_level}-{ruleset.max_level}"
            )
        if context.phase not in {phase.number for phase in ruleset.phases}:
            problems.append(f"{ruleset.label} has no phase {context.phase}")
        if context.content_mode not in {mode.mode for mode in ruleset.content_modes}:
            problems.append(f"{ruleset.label} has no {context.content_mode} content mode")
        class_def = ruleset.class_def(context.class_name)
        if context.race is not None and context.race not in class_def.races:
            problems.append(f"a {context.race} cannot be a {class_def.label}")
        if problems:
            raise DataValidationError("; ".join(problems))

    # --- items --------------------------------------------------------------------------

    def item(self, item_id: str) -> Item:
        item = self._items.get(item_id) if self._items is not None else None
        if item is None:
            raise NotFoundError(f"no item {item_id!r}")
        return item

    def _checked(self, items: Sequence[Item], ruleset: Ruleset) -> None:
        """Every item, wherever it came from, passes the same validation before scoring."""
        for item in items:
            report = validate_item(item, ruleset)
            if report.errors:
                problems = "; ".join(issue.message for issue in report.errors)
                raise DataValidationError(f"{item.name} cannot be scored: {problems}")

    # --- scoring and comparing ----------------------------------------------------------

    def score(
        self, item: Item, context: CharacterContext, *, replacing: Item | None = None
    ) -> ScoreResult:
        self.check(context)
        ruleset = self.ruleset(context.ruleset)
        self._checked([item, *([replacing] if replacing else [])], ruleset)
        return score_item(
            item, context, self.profile(context.profile_id), ruleset, replacing=replacing
        )

    def compare(
        self,
        items: Sequence[Item],
        context: CharacterContext,
        *,
        replacing: Item | None = None,
    ) -> ComparisonResult:
        """Rank and explain ``items`` (one or more) for ``context``."""
        self.check(context)
        ruleset = self.ruleset(context.ruleset)
        self._checked([*items, *([replacing] if replacing else [])], ruleset)
        return compare_items(
            items, context, self.profile(context.profile_id), ruleset, replacing=replacing
        )

    def compare_ids(
        self,
        item_ids: Sequence[str],
        context: CharacterContext,
        *,
        replacing_id: str | None = None,
    ) -> ComparisonResult:
        items = [self.item(item_id) for item_id in item_ids]
        replacing = self.item(replacing_id) if replacing_id else None
        return self.compare(items, context, replacing=replacing)
