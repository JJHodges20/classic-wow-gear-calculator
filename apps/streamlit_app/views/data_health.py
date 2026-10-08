"""The Settings / Data Health page (roadmap section 8): the ruleset, the item data and its
version, each provider's status, recent provider calls, the cache, and warnings."""

from __future__ import annotations

from html import escape

import streamlit as st

from components import layout
from components.html import Tone, chip, eyebrow, md
from views.common import open_workspace

STATUS_TONES: dict[str, Tone] = {"ok": "good", "info": "muted", "warning": "gold", "error": "bad"}
STATUS_WORDS = {"ok": "OK", "info": "Info", "warning": "Check", "error": "Problem"}


def render() -> None:
    layout.page_header(
        "Data health",
        "Whether everything is loaded and working: the configuration, the item data, each "
        "provider and the lookup cache.",
        "health",
    )
    ws = open_workspace()
    if ws is None:
        return
    health = ws.health
    checks = health.checks()
    counts = ws.search.counts()
    providers = health.provider_statuses()
    usable = [p for p in providers if p.usable and p.status == "active"]
    problems = [c for c in checks if c.status in ("warning", "error")]
    bundled = ws.bundled
    metadata = bundled.metadata

    st.html(
        layout.tiles_html(
            [
                layout.Tile(
                    "Ruleset",
                    f"{ws.ruleset.label} {ws.ruleset.version}",
                    context=ws.ruleset.validation_status,
                    text=True,
                ),
                layout.Tile(
                    "Item data",
                    bundled.version or "not loaded",
                    context=f"{sum(counts.values()):,} items",
                    text=True,
                ),
                layout.Tile(
                    "Providers ready",
                    f"{len(usable)} of {len(providers)}",
                    context="local data always works",
                ),
                layout.Tile(
                    "To look at",
                    str(len(problems)),
                    context="warnings and problems",
                    tone="bad" if problems else "",
                ),
            ]
        )
    )

    left, right = layout.split([1.15, 1], key="health")
    with left:
        layout.section("Checks")
        rows = "".join(
            f"<tr><td>{chip(STATUS_WORDS[c.status], STATUS_TONES[c.status])}</td>"
            f'<td class="wg-nowrap">{escape(c.name)}</td><td>{escape(c.detail)}</td></tr>'
            for c in checks
        )
        with layout.card("checks"):
            st.html(f'<table class="wg-table"><tbody>{rows}</tbody></table>')
        for problem in ws.profile_service.problems:
            st.warning(
                md(f"A saved profile could not be read: {problem}"), icon=":material/warning:"
            )

        layout.section("Cache")
        with layout.card("cache"):
            st.caption(
                f"{counts.get('cache', 0):,} items looked up online are kept for at most 30 "
                "days, as the Blizzard API terms require; when one expires its bundled version "
                "comes back."
            )
            if st.button("Drop expired lookups now", icon=":material/autorenew:"):
                dropped, restored = ws.refresh_cache()
                st.session_state["health_refreshed"] = (dropped, restored)
                st.rerun()
            refreshed = st.session_state.pop("health_refreshed", None)
            if refreshed is not None:
                dropped, restored = refreshed
                st.success(
                    f"Dropped {dropped} expired lookup(s); restored {restored} bundled item(s).",
                    icon=":material/check:",
                )
        with st.expander(f"Ruleset sources ({len(ws.ruleset.sources)})"):
            st.html(
                '<ul class="wg-list">'
                + "".join(
                    f'<li><a href="{escape(s.url)}" target="_blank" rel="noopener noreferrer">'
                    f"{escape(s.title)}</a></li>"
                    for s in ws.ruleset.sources
                )
                + "</ul>"
            )

    with right:
        layout.section("Bundled item data")
        facts = [
            ("Version", bundled.version or "not loaded"),
            ("Built", str(metadata.get("built_at", "-"))),
            ("Snapshot", str(metadata.get("snapshot", "-"))),
            ("Source", str(metadata.get("source", "-"))),
            ("License", str(metadata.get("license", "-"))),
            ("Curation", str(metadata.get("curation", "-"))),
            ("Phases", str(metadata.get("phase_heuristic", "-"))),
        ]
        rows = "".join(
            f'<tr><td class="wg-label">{escape(name)}</td><td>{escape(value)}</td></tr>'
            for name, value in facts
        )
        source_url = str(metadata.get("source_url", ""))
        link = (
            f'<a href="{escape(source_url)}" target="_blank" rel="noopener noreferrer">'
            "Snapshot release ↗</a>"
            if source_url.startswith("https://")
            else ""
        )
        with layout.card("bundled"):
            st.html(f'<table class="wg-table"><tbody>{rows}</tbody></table>{link}')
        by_phase = metadata.get("counts", {}).get("by_phase", {})
        if by_phase:
            with layout.card("phases"):
                st.html(eyebrow("Items by phase"))
                st.bar_chart(
                    {
                        "Items": {
                            f"Phase {phase}": count for phase, count in sorted(by_phase.items())
                        }
                    },
                    horizontal=True,
                    x_label="",
                    y_label="Items",
                    height=230,
                )

    layout.section("Providers", "Where items come from, in the order they are asked.")
    provider_rows = "".join(
        f'<tr><td class="wg-nowrap"><b>{escape(p.id)}</b></td>'
        f'<td class="wg-nowrap">{escape(p.kind)}</td>'
        f'<td class="wg-num">{p.priority}</td><td class="wg-nowrap">{escape(p.status)}</td>'
        f"<td>{'yes' if p.enabled else 'no'}</td>"
        f'<td class="wg-nowrap">{escape(p.credentials)}</td>'
        f"<td>{escape(p.description)}</td></tr>"
        for p in providers
    )
    with layout.card("providers"):
        st.html(
            '<table class="wg-table"><thead><tr><th>Provider</th><th>Kind</th>'
            '<th class="wg-num">Priority</th><th>Status</th><th>On</th><th>Credentials</th>'
            f"<th>What it does</th></tr></thead><tbody>{provider_rows}</tbody></table>"
        )
    calls = health.recent_calls(limit=15)
    layout.section("Recent provider calls")
    if calls:
        st.dataframe(
            [
                {
                    "When": f"{call.called_at:%Y-%m-%d %H:%M:%S}",
                    "Provider": call.provider,
                    "Call": f"{call.operation} {call.target}",
                    "Result": call.status,
                    "Detail": call.detail or "",
                    "Time (ms)": call.duration_ms,
                }
                for call in calls
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        layout.empty_state(
            "No provider has been called yet.",
            "Everything so far came from local data.",
            glyph="health",
        )
