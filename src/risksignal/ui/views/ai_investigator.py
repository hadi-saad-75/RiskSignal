"""Investigation page."""

from typing import Any

import streamlit as st

from risksignal.ui.components import LLM_HELP, banner, call_api, get_api_client, render_answer, system_selector
from risksignal.ui.formatting import (
    METRIC_LABELS,
    extract_simulation_metadata,
    format_amount,
    format_decimal,
)

STRESS_REQUEST = " Also compare the baseline with the SHARED_VENDOR_OUTAGE stress scenario."


def default_question(system_id: str) -> str:
    return (f"Investigate {system_id}. Review recent incidents, KRIs, controls and dependencies, run a baseline "
            "loss simulation, and identify questions that an Operational Risk analyst should investigate.")


def render_ai_investigator() -> None:
    banner()
    st.title("Investigation")
    st.markdown(
        "A language model selects among deterministic tools for retrieving system profiles, incidents, key "
        "risk indicators, controls, dependencies, and simulation results. It summarises the returned evidence "
        "and may suggest questions for further review. The model cannot modify records or make risk decisions. "
        "Reported quantitative claims are checked against the tool outputs; unmatched values are flagged."
    )
    client = get_api_client()
    health = call_api(client.health)
    if health is not None and not health["llm_configured"]:
        st.info(f"The language-model provider is not configured. {LLM_HELP}")

    system_id = system_selector(client, "agent")
    if system_id is None:
        return
    question = st.text_area(
        "Investigation request", value=default_question(system_id),
        key=f"agent_question_{system_id}", height=110,
    )
    include_stress = st.checkbox("Include the SHARED_VENDOR_OUTAGE stress scenario")

    if st.button("Investigate this system", type="primary"):
        text = question.strip() + (STRESS_REQUEST if include_stress else "")
        with st.spinner("Retrieving evidence and preparing the investigation summary..."):
            response = call_api(client.investigate, text)
        if response is not None:
            st.session_state["agent_response"] = response

    response = st.session_state.get("agent_response")
    if response:
        _show(response)
    else:
        st.caption("Run the investigation to display the evidence summary and tool activity.")


def _show(response: dict[str, Any]) -> None:
    st.divider()
    st.caption(f"Request: {response['question']}")
    if response["status"] != "completed":
        st.warning(f"The investigation did not complete normally (status: {response['status']}).")

    st.subheader("Investigation summary")
    render_answer(response["final_response"])
    for warning in response["warnings"]:
        st.warning(warning)

    _tool_activity(response["tool_activity"])
    _simulation_metadata(response["tool_activity"])
    st.caption(
        f"Provider: {response['provider']}. Language-model calls: {response['llm_calls']}. "
        f"{response['disclaimer']}"
    )


def _tool_activity(activities: list[dict[str, Any]]) -> None:
    st.subheader("Tool activity log")
    if not activities:
        st.write("No tools were called.")
        return
    for activity in activities:
        st.markdown(f"**{activity['step']}. {activity['status'].capitalize()}:** {activity['summary']}")
        with st.expander(f"Details: {activity['tool_name']}", expanded=False):
            st.caption(
                f"Started: {activity['started_at']}; duration: "
                f"{format_decimal(activity['duration_ms'], 0)} ms; status: {activity['status']}."
            )
            st.markdown("Input")
            st.json(activity["tool_input"])
            if activity.get("output") is not None:
                st.markdown("Tool output")
                st.json(activity["output"], expanded=False)


def _simulation_metadata(activities: list[dict[str, Any]]) -> None:
    meta = extract_simulation_metadata(activities)
    if meta is None:
        return
    st.subheader("Simulation metadata")
    st.caption(
        "Values are taken from the simulation tool output. The model is illustrative and uses synthetic data."
    )
    columns = st.columns(4)
    columns[0].metric("λ (incidents per year)", format_decimal(meta["lambda_used"]))
    columns[1].metric("μ", format_decimal(meta["severity_mu"], 3))
    columns[2].metric("σ", format_decimal(meta["severity_sigma"], 3))
    columns[3].metric("Simulations / seed", f"{meta['number_of_simulations']:,} / {meta['random_seed']}")
    st.caption(f"λ source: {meta['lambda_source']}. Severity fitted to {meta['severity_losses_used']} losses "
               f"(data source: {meta['severity_data_source']}).")
    rows = [{"Metric": label, "Baseline": format_amount(meta["baseline_metrics"][key]),
             **({"Stress": format_amount(meta["stress_metrics"][key])} if meta["stress_metrics"] else {})}
            for key, label in METRIC_LABELS]
    st.dataframe(rows, hide_index=True, width="stretch")
