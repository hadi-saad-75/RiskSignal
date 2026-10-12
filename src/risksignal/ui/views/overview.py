"""Page 1: Overview."""

import streamlit as st

from risksignal.ui.components import banner, call_api, get_api_client
from risksignal.ui.formatting import format_amount, label_for


def render_overview() -> None:
    banner()
    st.title("RiskSignal")
    st.markdown(
        "An **agentic Operational Risk investigation and stochastic scenario prototype** for technology "
        "risk. It combines a small synthetic dataset for a fictional bank, a dependency graph, a classical "
        "frequency-severity loss model with Monte Carlo simulation, and an AI investigator that gathers "
        "evidence only through deterministic tools. The AI never calculates risk numbers itself and makes "
        "no risk decisions."
    )

    overview = call_api(get_api_client().overview, 10)
    if overview is None:
        return
    counts = overview["counts"]

    columns = st.columns(5)
    for column, (label, key) in zip(columns, [("Systems", "systems"), ("Business processes", "processes"),
                                              ("Vendors", "vendors"), ("Controls", "controls"),
                                              ("Incidents", "incidents")]):
        column.metric(label, format_amount(counts[key]))
    st.caption(
        f"Synthetic Atlas Bank (fictional). Incidents recorded {counts['data_window_start']} to "
        f"{counts['data_window_end']}; {format_amount(counts['kri_observations'])} monthly KRI observations."
    )

    st.subheader("Recent synthetic incidents")
    st.dataframe(
        [{"Date": i["date"], "Incident": i["incident_id"], "System": i["system_id"], "Category": label_for(i["category"]),
          "Severity": i["severity"], "Loss": i["financial_loss"], "Description": i["description"]}
         for i in overview["recent_incidents"]],
        hide_index=True, width="stretch",
        column_config={"Loss": st.column_config.NumberColumn("Loss", format="%d")},
    )

    st.subheader("Where to go next")
    st.markdown(
        "- **System Explorer**: profile, incidents, KRIs, controls and dependencies of one system.\n"
        "- **Scenario Lab**: baseline and stress loss simulations with explicit, illustrative assumptions.\n"
        "- **AI Investigator**: ask the agent to investigate a system; see its answer and every tool it used."
    )
