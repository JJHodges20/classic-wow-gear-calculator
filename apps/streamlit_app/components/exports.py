"""Downloads of a comparison: JSON and CSV to check or reuse it, an HTML report to share it.
The files are formatted by ``wow_gear.reporting``; nothing here changes a number."""

from __future__ import annotations

import streamlit as st

from wow_gear.models.character import CharacterContext
from wow_gear.models.comparison import ComparisonResult
from wow_gear.reporting.export import (
    comparison_csv,
    comparison_html,
    comparison_json,
    components_csv,
)


def comparison_downloads(
    result: ComparisonResult, context: CharacterContext | None, key: str
) -> None:
    """An Export menu for ``result``; ``key`` keeps the buttons of each page apart."""
    name = f"comparison_{result.fingerprint[:10]}"
    with st.popover("Export", icon=":material/download:"):
        st.caption(
            "The JSON file is the whole result; the CSV files are the ranking and every score "
            "component; the report is one page to share."
        )
        files = (
            ("Result (JSON)", comparison_json(result), "json", "application/json", "data_object"),
            ("Ranking (CSV)", comparison_csv(result), "csv", "text/csv", "table"),
            ("Components (CSV)", components_csv(result), "components.csv", "text/csv", "table"),
            ("Report (HTML)", comparison_html(result, context), "html", "text/html", "description"),
        )
        for label, data, suffix, mime, icon in files:
            st.download_button(
                label,
                data,
                file_name=f"{name}.{suffix}",
                mime=mime,
                key=f"{key}_{suffix}",
                icon=f":material/{icon}:",
                on_click="ignore",
                width="stretch",
            )
