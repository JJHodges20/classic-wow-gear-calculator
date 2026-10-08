"""The Gear Set page (roadmap V1.5): a saved character with a full set of gear - what the gear
is worth piece by piece, where its caps stand, what it lacks, and how one change moves the
whole character. It calls services only and does no game math."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from pathlib import PurePath

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from components import gear as show
from components import recommendation
from components.context_bar import phase_label
from components.html import chip, eyebrow, md
from components.item_input import picker
from state import session
from views.common import open_workspace
from wow_gear.models.enums import WEAPON_SKILL_STATS, EquipmentSlot, ItemSlot, Stat
from wow_gear.models.gear import (
    BLOCKS_OFF_HAND,
    EQUIPMENT_SLOTS,
    GearAnalysis,
    ReplacementResult,
    SavedCharacter,
)
from wow_gear.models.labels import CONTENT_MODE_LABELS, EQUIPMENT_SLOT_LABELS, ROLE_LABELS
from wow_gear.models.profile import BuildProfile
from wow_gear.services.characters import CharacterService, LoadedGear
from wow_gear.services.errors import DataValidationError, NotFoundError, WowGearError
from wow_gear.services.workspace import Workspace

WORKING = "gear_working"
"""The character being edited: a SavedCharacter, saved or not."""
LOADED = "gear_loaded"
"""The choice the working copy was loaded from (a saved id, or NEW)."""
CHOICE = "gear_choice"
NEXT = "gear_next"
"""The choice to select on the next run (a widget's value cannot change once it is drawn)."""
FLASH = "gear_flash"
GEN = "gear_gen"
"""Goes up when a character is loaded, so the detail fields start from its values."""
EDIT = "gear_edit_slot"
ROUND = "gear_round"
TRY_SLOT = "gear_try_slot"
TRY = "gear_try"
TRY_ROUND = "gear_try_round"
IMPORTED = "gear_imported"
CACHE = "gear_cache"
NEW = "__new__"
CALCULATOR = "pages/calculator.py"

LEFT = (
    EquipmentSlot.HEAD,
    EquipmentSlot.NECK,
    EquipmentSlot.SHOULDER,
    EquipmentSlot.BACK,
    EquipmentSlot.CHEST,
    EquipmentSlot.WRIST,
    EquipmentSlot.MAIN_HAND,
    EquipmentSlot.OFF_HAND,
    EquipmentSlot.RANGED,
)
RIGHT = (
    EquipmentSlot.HANDS,
    EquipmentSlot.WAIST,
    EquipmentSlot.LEGS,
    EquipmentSlot.FEET,
    EquipmentSlot.FINGER_1,
    EquipmentSlot.FINGER_2,
    EquipmentSlot.TRINKET_1,
    EquipmentSlot.TRINKET_2,
)


def _fits(slot: EquipmentSlot) -> tuple[ItemSlot, ...]:
    """The item slots that can be worn in ``slot``."""
    return tuple(item_slot for item_slot, places in EQUIPMENT_SLOTS.items() if slot in places)


def _core(character: SavedCharacter) -> dict[str, object]:
    return character.model_dump(mode="json", exclude={"version", "saved_at"})


def _profile_label(ws: Workspace, profile: BuildProfile) -> str:
    ruleset = ws.profile_service.ruleset_of(profile)
    custom = " (yours)" if ws.profile_service.is_custom(profile.id) else ""
    return (
        f"{ruleset.class_def(profile.class_name).label} · {ROLE_LABELS[profile.role]} · "
        f"{profile.label}{custom}"
    )


# --- choosing and loading a character ------------------------------------------------


def _fresh(ws: Workspace) -> SavedCharacter:
    """A new character for the class and profile chosen on the calculator, if any."""
    service, calc = ws.characters, ws.calculator
    profile_id = session.get(session.PROFILE)
    known = {profile.id for profile in ws.profile_service.all()}
    if profile_id not in known:
        profile_id = ws.profile_service.all()[0].id
    choices = {
        "race": session.get(session.RACE),
        "level": session.get(session.LEVEL),
        "phase": session.get(session.PHASE),
        "content_mode": session.get(session.CONTENT),
    }
    try:
        return service.new("New character", str(profile_id), **choices)
    except DataValidationError:
        return service.new("New character", calc.profile(str(profile_id)).id)


def _load(ws: Workspace, choice: str) -> None:
    working = _fresh(ws) if choice == NEW else ws.characters.get(choice)
    st.session_state[WORKING] = working
    st.session_state[LOADED] = choice
    st.session_state[GEN] = int(st.session_state.get(GEN, 0)) + 1
    for key in (EDIT, TRY):
        st.session_state.pop(key, None)


def _choose(ws: Workspace) -> SavedCharacter | None:
    service = ws.characters
    saved = service.all()
    for problem in service.problems:
        st.warning(md(problem), icon=":material/warning:")
    options = [character.id for character in saved] + [NEW]
    pending = st.session_state.pop(NEXT, None)
    if pending in options:
        st.session_state[CHOICE] = pending
    session.default(CHOICE, saved[0].id if saved else NEW)
    session.keep_valid(CHOICE, options, NEW)
    names = {character.id: character for character in saved}
    working = st.session_state.get(WORKING)
    unsaved_new = st.session_state.get(LOADED) == NEW and isinstance(working, SavedCharacter)

    def label(option: str) -> str:
        if option == NEW:
            return f"{working.name} (not saved yet)" if unsaved_new and working else "New character"
        character = names[option]
        return f"{character.name} · level {character.level} {character.class_name.value}"

    columns = st.columns([2.2, 1, 1, 1, 1], vertical_alignment="bottom")
    choice = columns[0].selectbox("Character", options, format_func=label, key=CHOICE)
    if choice is None:
        return None
    if st.session_state.get(LOADED) != choice or not isinstance(working, SavedCharacter):
        try:
            _load(ws, choice)
        except (NotFoundError, DataValidationError) as error:
            st.error(md(f"This character cannot be opened: {error}"), icon=":material/error:")
            return None
    working = st.session_state[WORKING]
    assert isinstance(working, SavedCharacter)
    _actions(ws, working, columns[1:])
    return working


def _actions(ws: Workspace, working: SavedCharacter, columns: Sequence[DeltaGenerator]) -> None:
    service = ws.characters
    stored = st.session_state.get(LOADED) != NEW
    if columns[0].button(
        "Save", key="gear_save", type="primary", icon=":material/save:", width="stretch"
    ):
        to_save = working
        if not stored:
            to_save = working.model_copy(update={"id": service.free_id(working.name)})
        try:
            saved = service.save(to_save)
        except (DataValidationError, NotFoundError) as error:
            st.error(md(f"Not saved: {error}"), icon=":material/error:")
        else:
            st.session_state[WORKING] = saved
            st.session_state[LOADED] = saved.id
            st.session_state[NEXT] = saved.id
            st.session_state[FLASH] = f"Saved {saved.name} (version {saved.version})."
            st.rerun()
    if columns[1].button("New", key="gear_new", icon=":material/person_add:", width="stretch"):
        st.session_state[NEXT] = NEW
        st.session_state[LOADED] = None
        st.rerun()
    with columns[2].popover("Import", icon=":material/upload:", width="stretch"):
        _import(service, working)
    with columns[3].popover(
        "Delete", icon=":material/delete:", width="stretch", disabled=not stored
    ):
        st.write(
            md(f"Delete {working.name}? This cannot be undone; export it first to keep a copy.")
        )
        if st.button("Delete it", type="primary", key="gear_delete_confirm"):
            service.delete(working.id)
            st.session_state[NEXT] = NEW
            st.session_state[LOADED] = None
            st.session_state[FLASH] = f"Deleted {working.name}."
            st.rerun()


def _import(service: CharacterService, working: SavedCharacter) -> None:
    st.caption(
        "A character exported as JSON becomes a new character; a CSV gear list (slot and "
        "item_id columns) replaces this character's gear. Nothing is saved until you save."
    )
    upload = st.file_uploader(
        "Character (JSON) or gear list (CSV)", type=["json", "csv"], key="gear_upload"
    )
    if upload is None or st.session_state.get(IMPORTED) == upload.file_id:
        return
    st.session_state[IMPORTED] = upload.file_id
    suffix = PurePath(upload.name).suffix.lower()
    try:
        text = upload.getvalue().decode("utf-8-sig")
        character = service.import_text(text, suffix, into=working)
    except UnicodeDecodeError:
        st.error("The file is not UTF-8 text.", icon=":material/error:")
        return
    except (DataValidationError, NotFoundError) as error:
        st.error(md(f"Not imported: {error}"), icon=":material/error:")
        return
    st.session_state[WORKING] = character
    if suffix == ".json":
        st.session_state[NEXT] = NEW
        st.session_state[LOADED] = NEW
        st.session_state[GEN] = int(st.session_state.get(GEN, 0)) + 1
        st.session_state[FLASH] = f"Imported {character.name}. Save it to keep it."
    else:
        st.session_state[FLASH] = "Imported the gear list. Save to keep it."
    st.rerun()


# --- the character's details ----------------------------------------------------------


def _details(ws: Workspace, working: SavedCharacter) -> SavedCharacter:
    service, calc = ws.characters, ws.calculator
    gen = int(st.session_state.get(GEN, 0))
    profiles = {profile.id: profile for profile in ws.profile_service.all()}
    options = list(profiles)
    if working.profile_id not in profiles:
        options.append(working.profile_id)
        st.warning(
            f"The profile {working.profile_id} no longer exists: choose another build profile.",
            icon=":material/warning:",
        )
    ruleset = calc.ruleset(working.ruleset)
    with st.container(border=True):
        columns = st.columns([1.4, 2.3, 1.1, 0.7, 1.5, 1.0], vertical_alignment="bottom")
        name = columns[0].text_input(
            "Name", value=working.name, max_chars=60, key=f"gear_name_{gen}"
        )
        profile_id = columns[1].selectbox(
            "Build profile",
            options,
            index=options.index(working.profile_id),
            format_func=lambda key: (
                _profile_label(ws, profiles[key]) if key in profiles else f"{key} (missing)"
            ),
            key=f"gear_profile_{gen}",
            help="The stat weights, caps and assumptions the gear is valued with.",
        )
        class_name = profiles[profile_id].class_name if profile_id in profiles else None
        races = list(ruleset.class_def(class_name).races) if class_name else []
        race_key = f"gear_race_{gen}"
        session.keep_valid(race_key, [None, *races], None)
        race = columns[2].selectbox(
            "Race",
            [None, *races],
            index=[None, *races].index(working.race) if working.race in races else 0,
            format_func=lambda value: (
                "Not given" if value is None else ruleset.race_def(value).label
            ),
            key=race_key,
            help="Racial weapon skill moves the hit cap.",
        )
        level = columns[3].number_input(
            "Level",
            min_value=ruleset.min_level,
            max_value=ruleset.max_level,
            value=working.level,
            step=1,
            key=f"gear_level_{gen}",
        )
        phases = [phase.number for phase in ruleset.phases]
        phase = columns[4].selectbox(
            "Phase",
            phases,
            index=phases.index(working.phase) if working.phase in phases else 0,
            format_func=lambda number: phase_label(ruleset, number),
            key=f"gear_phase_{gen}",
        )
        modes = [mode.mode for mode in ruleset.content_modes]
        content = columns[5].selectbox(
            "Content",
            modes,
            index=modes.index(working.content_mode) if working.content_mode in modes else 0,
            format_func=lambda value: CONTENT_MODE_LABELS[value],
            key=f"gear_content_{gen}",
        )
    changes: dict[str, object] = {}
    clean = " ".join(name.split())
    if clean and clean != working.name:
        changes["name"] = clean
    if not clean:
        st.caption("A character needs a name; the last one is kept.")
    for key, value, old in (
        ("profile_id", profile_id, working.profile_id),
        ("race", race, working.race),
        ("level", int(level) if level is not None else working.level, working.level),
        ("phase", phase, working.phase),
        ("content_mode", content, working.content_mode),
    ):
        if (value is not None and value != old) or (key == "race" and value != old):
            changes[key] = value
    if not changes:
        return working
    try:
        updated = service.update(working, **changes)
    except (DataValidationError, NotFoundError) as error:
        st.error(md(f"Not applied: {error}"), icon=":material/error:")
        return working
    st.session_state[WORKING] = updated
    return updated


# --- the gear -------------------------------------------------------------------------


def _analyse(
    service: CharacterService, working: SavedCharacter, profile_version: str
) -> tuple[GearAnalysis, LoadedGear]:
    """The analysis, computed once for each version of the character and its profile."""
    key = (working.model_dump_json(), profile_version)
    cached = st.session_state.get(CACHE)
    if isinstance(cached, tuple) and cached[0] == key:
        return cached[1]  # type: ignore[no-any-return]
    result = service.analyse(working)
    st.session_state[CACHE] = (key, result)
    return result


def _slot_row(
    ws: Workspace,
    working: SavedCharacter,
    loaded: LoadedGear,
    analysis: GearAnalysis | None,
    slot: EquipmentSlot,
) -> None:
    item = loaded.items.get(slot)
    values = {value.slot: value for value in analysis.slots} if analysis else {}
    note = None
    main = loaded.items.get(EquipmentSlot.MAIN_HAND)
    if item is None and slot in working.gear.items:
        note = f"Item {working.gear.items[slot]} is not in the item data"
    elif slot == EquipmentSlot.OFF_HAND and main is not None and main.slot in BLOCKS_OFF_HAND:
        note = f"Taken by {main.name}"
    editing = st.session_state.get(EDIT) == slot
    unit = analysis.unit_abbreviation if analysis else ""
    worth = show.worth_chip(values.get(slot), unit)
    info, action = st.columns([3.4, 1], vertical_alignment="center", gap="small")
    info.html(show.slot_html(slot, item, worth, note))
    label = "Close" if editing else ("Change" if item is not None else "Add")
    if action.button(label, key=f"gear_change_{slot.value}", type="tertiary", width="stretch"):
        st.session_state[EDIT] = None if editing else slot
        st.rerun()
    if editing:
        _slot_editor(ws, working, slot, item is not None or slot in working.gear.items)


def _slot_editor(ws: Workspace, working: SavedCharacter, slot: EquipmentSlot, worn: bool) -> None:
    with st.container(border=True):
        st.html(eyebrow(f"Choose an item for {EQUIPMENT_SLOT_LABELS[slot].lower()}"))
        round_number = int(st.session_state.get(ROUND, 0))
        picked = picker(f"gear{round_number}", ws, fits=_fits(slot))
        if worn and st.button("Empty this slot", key=f"gear_empty_{slot.value}"):
            st.session_state[WORKING] = ws.characters.equip(working, slot, None)
            st.session_state[EDIT] = None
            st.rerun()
        if picked is not None:
            try:
                st.session_state[WORKING] = ws.characters.equip(working, slot, picked.id)
            except (DataValidationError, NotFoundError) as error:
                st.error(md(f"{picked.name} cannot go there: {error}"), icon=":material/error:")
                return
            st.session_state[EDIT] = None
            st.session_state[ROUND] = round_number + 1
            st.rerun()


def _grid(
    ws: Workspace, working: SavedCharacter, loaded: LoadedGear, analysis: GearAnalysis | None
) -> None:
    left, right = st.columns(2, gap="medium")
    for column, slots in ((left, LEFT), (right, RIGHT)):
        with column:
            for slot in slots:
                with st.container(border=True):
                    _slot_row(ws, working, loaded, analysis, slot)


# --- the analysis ---------------------------------------------------------------------


def _list(entries: list[str] | tuple[str, ...]) -> str:
    return '<ul class="wg-list">' + "".join(f"<li>{escape(e)}</li>" for e in entries) + "</ul>"


def _summary(analysis: GearAnalysis, loaded: LoadedGear, profile: BuildProfile) -> None:
    unit = analysis.unit_abbreviation
    worn = len(loaded.items)
    reached = sum(1 for status in analysis.caps if status.state != "short")
    tiles = [
        show.tile("Gear value", f"{analysis.score:.1f}", unit),
        show.tile("Pieces worn", f"{worn} of {worn + len(analysis.empty)}"),
    ]
    if analysis.caps:
        tiles.append(show.tile("Caps reached", f"{reached} of {len(analysis.caps)}"))
    with st.container(border=True):
        st.html(
            eyebrow(f"Under {profile.label}")
            + '<div class="wg-tiles">'
            + "".join(tiles)
            + "</div>"
            + '<div class="wg-small">A piece is worth what the character would lose without it, '
            "with the rest of the gear as it is. Valued under this profile and its assumptions."
            "</div>"
        )


def _panel(
    ws: Workspace, analysis: GearAnalysis, loaded: LoadedGear, profile: BuildProfile
) -> None:
    ruleset = ws.calculator.ruleset(analysis.ruleset_id)
    _summary(analysis, loaded, profile)
    st.html(eyebrow("Caps and breakpoints") + show.caps_html(analysis.caps))
    if analysis.under_served:
        st.html(eyebrow("Under-served priorities") + _list(analysis.under_served))
    if analysis.weakest:
        st.html(
            eyebrow("Weakest pieces")
            + _list(
                [
                    f"{EQUIPMENT_SLOT_LABELS[weak.slot]} · {weak.item_name}: {weak.reason}"
                    for weak in analysis.weakest
                ]
            )
        )
    if analysis.not_valued:
        st.html(
            eyebrow("Not valued by this profile")
            + '<div class="wg-chips">'
            + "".join(chip(text, "muted") for text in analysis.not_valued)
            + "</div>"
        )
    st.html(eyebrow("Where the value comes from") + show.value_table(analysis, ruleset))
    for note in analysis.notes:
        if "not usable" in note:
            st.error(md(note), icon=":material/block:")
        else:
            st.info(md(note), icon=":material/info:")
    if analysis.not_scored:
        st.html(
            '<div class="wg-small">Not scored in version 1:</div>'
            + '<div class="wg-small">'
            + "<br>".join(escape(text) for text in analysis.not_scored)
            + "</div>"
        )
    with st.expander("Assumptions", icon=":material/rule:"):
        st.html(_list(analysis.assumptions))


# --- trying a replacement -------------------------------------------------------------


def _try(ws: Workspace, working: SavedCharacter, loaded: LoadedGear) -> ReplacementResult | None:
    st.html(eyebrow("Try a replacement"))
    tried: ReplacementResult | None = None
    with st.container(border=True):
        left, right = st.columns([1, 1.3], gap="large")
        with left:
            slot = st.selectbox(
                "Slot to change",
                list(EquipmentSlot),
                format_func=lambda value: EQUIPMENT_SLOT_LABELS[value],
                key=TRY_SLOT,
            )
            if slot is None:
                return None
            now = loaded.items.get(slot)
            st.caption(md(f"Now: {now.name}.") if now is not None else "Now: empty.")
            round_number = int(st.session_state.get(TRY_ROUND, 0))
            picked = picker(f"try{round_number}", ws, fits=_fits(slot))
            if picked is not None:
                st.session_state[TRY] = (slot, picked.id)
                st.session_state[TRY_ROUND] = round_number + 1
                st.rerun()
        with right:
            pending = st.session_state.get(TRY)
            if not (isinstance(pending, tuple) and pending[0] == slot):
                st.html(
                    '<div class="wg-empty"><b>Search for an item to try.</b> The whole '
                    "character is valued with it and without it, so caps the rest of the gear "
                    "fills, a two-hander replacing two weapons and a weapon that moves the hit "
                    "cap are all counted.</div>"
                )
                return None
            try:
                tried = ws.characters.try_replacement(working, slot, pending[1])
            except (DataValidationError, NotFoundError) as error:
                st.error(md(f"This cannot be tried: {error}"), icon=":material/error:")
                return None
            _tried(ws, working, tried)
    return tried


def _tried(ws: Workspace, working: SavedCharacter, tried: ReplacementResult) -> None:
    st.html(show.replacement_html(tried))
    if tried.lines:
        st.html(
            '<ul class="wg-why">'
            + "".join(recommendation.line_html(line) for line in tried.lines)
            + "</ul>"
        )
    changes = show.cap_changes(tried)
    if changes:
        st.html(eyebrow("Caps") + _list(changes))
    for note in tried.notes:
        st.info(md(note), icon=":material/info:")
    buttons = st.container(horizontal=True)
    if buttons.button("Put it on", type="primary", icon=":material/check:", key="gear_try_equip"):
        try:
            st.session_state[WORKING] = ws.characters.equip(working, tried.slot, tried.candidate_id)
        except (DataValidationError, NotFoundError) as error:
            st.error(md(f"Not put on: {error}"), icon=":material/error:")
            return
        st.session_state.pop(TRY, None)
        st.session_state[FLASH] = f"{tried.candidate_name} is on. Save to keep the change."
        st.rerun()
    if buttons.button("Clear", icon=":material/close:", key="gear_try_clear"):
        st.session_state.pop(TRY, None)
        st.rerun()


# --- totals, the calculator and files -------------------------------------------------


def _use_in_calculator(ws: Workspace, working: SavedCharacter, analysis: GearAnalysis) -> None:
    calc = ws.calculator
    profile = calc.profile(working.profile_id)
    st.session_state[session.CLASS] = profile.class_name
    st.session_state[session.ROLE] = profile.role
    st.session_state[session.PROFILE] = profile.id
    st.session_state[session.PHASE] = working.phase
    st.session_state[session.LEVEL] = working.level
    st.session_state[session.CONTENT] = working.content_mode
    st.session_state[session.RACE] = working.race
    main = ws.characters.load_gear(working).items.get(EquipmentSlot.MAIN_HAND)
    weapon = main.weapon_type if main is not None else None
    st.session_state[session.MAIN_HAND] = weapon if weapon in WEAPON_SKILL_STATS else None
    st.session_state[session.EQUIPPED] = session.NEITHER
    asked: set[Stat] = {*calc.gear_total_stats(profile.id), *WEAPON_SKILL_STATS.values()}
    for stat in asked | set(analysis.totals):
        st.session_state[session.total_key(stat)] = float(analysis.totals.get(stat, 0.0))
    st.switch_page(CALCULATOR)


def _files(
    ws: Workspace,
    working: SavedCharacter,
    analysis: GearAnalysis | None,
    tried: ReplacementResult | None,
) -> None:
    service = ws.characters
    st.caption(
        "The JSON file is the whole character and imports back; the CSV is the gear list; the "
        "report is one page to share, with the replacement you are trying if there is one."
    )
    buttons = st.container(horizontal=True)
    buttons.download_button(
        "Character (JSON)",
        service.export_json(working),
        file_name=f"{working.id}.json",
        mime="application/json",
        icon=":material/data_object:",
    )
    buttons.download_button(
        "Gear list (CSV)",
        service.export_csv(working, analysis),
        file_name=f"{working.id}_gear.csv",
        mime="text/csv",
        icon=":material/table:",
    )
    if analysis is not None:
        buttons.download_button(
            "Report (HTML)",
            service.export_html(working, analysis, tried),
            file_name=f"{working.id}_report.html",
            mime="text/html",
            icon=":material/description:",
        )


def render() -> None:
    ws = open_workspace()
    if ws is None:
        return
    flash = st.session_state.pop(FLASH, None)
    if flash:
        st.success(md(flash), icon=":material/check:")
    st.write("")
    try:
        working = _choose(ws)
    except WowGearError as error:
        st.error(md(f"Saved characters cannot be read: {error}"), icon=":material/error:")
        return
    if working is None:
        return
    try:
        working = _details(ws, working)
    except WowGearError as error:
        st.error(md(f"This character cannot be shown: {error}"), icon=":material/error:")
        return
    saved_copy = None
    if st.session_state.get(LOADED) != NEW:
        try:
            saved_copy = ws.characters.get(working.id)
        except NotFoundError:  # deleted elsewhere, say from the command line
            st.warning(md(f"{working.name} is no longer saved."), icon=":material/warning:")
    if saved_copy is None or _core(saved_copy) != _core(working):
        st.html(
            '<div class="wg-small">'
            + chip("Unsaved changes", "gold")
            + " Save to keep them; they stay while you use other pages.</div>"
        )

    analysis: GearAnalysis | None = None
    loaded = ws.characters.load_gear(working)
    profile: BuildProfile | None = None
    try:
        profile = ws.calculator.profile(working.profile_id)
        analysis, loaded = _analyse(ws.characters, working, profile.version)
    except (DataValidationError, NotFoundError) as error:
        st.error(md(f"This gear cannot be analysed: {error}"), icon=":material/error:")

    st.write("")
    gear_column, analysis_column = st.columns([1.25, 1], gap="large")
    with gear_column:
        st.html(eyebrow(f"Gear · {len(loaded.items)} pieces"))
        _grid(ws, working, loaded, analysis)
    with analysis_column:
        st.html(eyebrow("Analysis"))
        if analysis is None or profile is None:
            st.html('<div class="wg-empty"><b>No analysis.</b> Fix the problem above.</div>')
        elif not loaded.items:
            st.html(
                '<div class="wg-empty"><b>Add your gear to analyse it.</b>'
                "<ol><li>Choose the build profile and race above.</li>"
                "<li>Use <i>Add</i> on each slot to search for the item you wear, or import "
                "a gear list.</li><li>Save the character to keep it.</li></ol></div>"
            )
        else:
            _panel(ws, analysis, loaded, profile)

    st.write("")
    tried = _try(ws, working, loaded) if loaded.items or working.gear.items else None

    st.write("")
    with st.expander("Totals from this gear", icon=":material/functions:"):
        if analysis is None:
            st.caption("Totals show once the gear can be analysed.")
        else:
            ruleset = ws.calculator.ruleset(analysis.ruleset_id)
            st.html(show.totals_table(analysis.totals, ruleset))
            st.caption(
                "These are the tooltip totals of the gear. The calculator can use them as your "
                "current gear totals, so its caps start where this gear stands."
            )
            if st.button(
                "Use these totals in the calculator",
                key="gear_use_totals",
                icon=":material/calculate:",
            ):
                _use_in_calculator(ws, working, analysis)
    with st.expander("Export", icon=":material/download:"):
        _files(ws, working, analysis, tried)
