"""The Settings / Data Health page (roadmap section 8): the ruleset, the item data and its
version, each provider's status, recent provider calls, the cache, and warnings."""

from __future__ import annotations

from html import escape

import streamlit as st

from components.html import Tone, chip, eyebrow, md
from views.common import open_workspace

STATUS_TONES: dict[str, Tone] = {"ok": "good", "info": "muted", "warning": "gold", "error": "bad"}
STATUS_WORDS = {"ok": "OK", "info": "Info", "warning": "Check", "error": "Problem"}


def _tile(label: str, value: str, note: str = "") -> str:
    return (
        f'<div class="wg-tile"><div class="wg-tile-label">{escape(label)}</div>'
        f'<div class="wg-tile-value" style="font-size:1.35rem">{escape(value)}</div>'
        + (f'<div class="wg-small">{escape(note)}</div>' if note else "")
        + "</div>"
    )


def render() -> None:
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

    st.write("")
    st.html(
        '<div class="wg-tiles">'
        + _tile("Ruleset", f"{ws.ruleset.label} {ws.ruleset.version}", ws.ruleset.validation_status)
        + _tile("Item data", bundled.version or "not loaded", f"{sum(counts.values()):,} items")
        + _tile("Providers ready", f"{len(usable)} of {len(providers)}", "local data always works")
        + _tile("To look at", str(len(problems)), "warnings and problems")
        + "</div>"
    )

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        rows = "".join(
            f"<tr><td>{chip(STATUS_WORDS[c.status], STATUS_TONES[c.status])}</td>"
            f"<td>{escape(c.name)}</td><td>{escape(c.detail)}</td></tr>"
            for c in checks
        )
        st.html(eyebrow("Checks") + f'<table class="wg-table"><tbody>{rows}</tbody></table>')
        for problem in ws.profile_service.problems:
            st.warning(
                md(f"A saved profile could not be read: {problem}"), icon=":material/warning:"
            )

    with right:
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
            f"<tr><td>{escape(name)}</td><td>{escape(value)}</td></tr>" for name, value in facts
        )
        source_url = str(metadata.get("source_url", ""))
        link = (
            f'<a href="{escape(source_url)}" target="_blank" rel="noopener noreferrer">'
            "Snapshot release ↗</a>"
            if source_url.startswith("https://")
            else ""
        )
        st.html(
            eyebrow("Bundled item data")
            + f'<table class="wg-table"><tbody>{rows}</tbody></table>{link}'
        )
        by_phase = metadata.get("counts", {}).get("by_phase", {})
        if by_phase:
            st.html(eyebrow("Items by phase"))
            st.bar_chart(
                {"Items": {f"Phase {phase}": count for phase, count in sorted(by_phase.items())}},
                height=220,
                color="#B08A3E",
            )

        st.html(eyebrow("Cache"))
        st.caption(
            f"{counts.get('cache', 0):,} items looked up online are kept for at most 30 days, as "
            "the Blizzard API terms require; when one expires its bundled version comes back."
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
                "<ul>"
                + "".join(
                    f'<li><a href="{escape(s.url)}" target="_blank" rel="noopener noreferrer">'
                    f"{escape(s.title)}</a></li>"
                    for s in ws.ruleset.sources
                )
                + "</ul>"
            )

    provider_rows = "".join(
        f"<tr><td>{escape(p.id)}</td><td>{escape(p.kind)}</td>"
        f'<td class="wg-num">{p.priority}</td><td>{escape(p.status)}</td>'
        f"<td>{'yes' if p.enabled else 'no'}</td><td>{escape(p.credentials)}</td>"
        f"<td>{escape(p.description)}</td></tr>"
        for p in providers
    )
    st.html(
        eyebrow("Providers") + '<table class="wg-table"><thead><tr><th>Provider</th><th>Kind</th>'
        '<th class="wg-num">Priority</th><th>Status</th><th>On</th><th>Credentials</th>'
        f"<th>What it does</th></tr></thead><tbody>{provider_rows}</tbody></table>"
    )
    calls = health.recent_calls(limit=15)
    st.html(eyebrow("Recent provider calls"))
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
        st.caption("No provider has been called yet: everything so far came from local data.")
