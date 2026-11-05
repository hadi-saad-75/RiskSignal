"""Investigation section of the Assistant page: a full, tool-based investigation of one system.

The request goes to ``POST /agent/investigate``. The agent calls the deterministic tools, and the
page shows the sectioned summary, the tool activity log and the simulation metadata read from
the tool output.
"""

from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    call_api,
    label,
    render_answer,
    rule,
    section_header,
    spacer,
    system_selector,
)
from risksignal.ui.formatting import (
    LOSS_UNIT_NOTICE,
    METRIC_LABELS,
    display_prose,
    extract_simulation_metadata,
    format_amount,
    format_decimal,
)
from risksignal.text import normalize_prose

STRESS_REQUEST = " Also compare the baseline with the SHARED_VENDOR_OUTAGE stress scenario."
RESPONSE_KEY = "agent_response"


def default_question(system_id: str) -> str:
    return (f"Investigate {system_id}. Review recent incidents, KRIs, controls and dependencies, run a baseline "
            "loss simulation, and identify questions that an Operational Risk analyst should investigate.")


def render_investigation(client: ApiClient) -> None:
    st.caption(LOSS_UNIT_NOTICE)
    section_header("Request", "Choose a system and describe what should be examined. The request is sent "
                   "to the investigation agent exactly as written.", index="01")
    controls, _, request = st.columns([5, 1, 6])
    with controls:
        system_id = system_selector(client, "agent")
    if system_id is None:
        return
    with controls:
        include_stress = st.checkbox("Include the SHARED_VENDOR_OUTAGE stress scenario")
    with request:
        question = st.text_area(
            "Investigation request", value=default_question(system_id),
            key=f"agent_question_{system_id}", height=150,
        )
        run = st.button("Investigate this system", type="primary")

    if run:
        text = question.strip() + (STRESS_REQUEST if include_stress else "")
        with st.spinner("Retrieving evidence and preparing the investigation summary..."):
            response = call_api(client.investigate, text)
        if response is not None:
            st.session_state[RESPONSE_KEY] = response

    response = st.session_state.get(RESPONSE_KEY)
    if response:
        _show(response)
    else:
        spacer()
        st.caption("Run the investigation to display the evidence summary and tool activity.")


def _show(response: dict[str, Any]) -> None:
    aside = section_header("Investigation summary", index="02")
    with aside:
        st.caption(normalize_prose(f"Request: {response['question']}"))
    if response["status"] != "completed":
        st.warning(f"The investigation did not complete normally (status: {response['status']}).")

    render_answer(response["final_response"])
    for warning in response["warnings"]:
        st.warning(normalize_prose(warning))

    _tool_activity(response["tool_activity"])
    _simulation_metadata(response["tool_activity"])
    rule(subtle=True)
    spacer()
    st.caption(normalize_prose(
        f"Provider: {response['provider']}. Language-model calls: {response['llm_calls']}. "
        f"{response['disclaimer']}"
    ))


def _tool_activity(activities: list[dict[str, Any]]) -> None:
    section_header("Tool activity log", "Every deterministic tool the agent called, in order, with its "
                   "input and output.", index="03")
    if not activities:
        st.write("No tools were called.")
        return
    for activity in activities:
        st.markdown(normalize_prose(f"**{activity['step']}. {activity['status'].capitalize()}:** {activity['summary']}"))
        with st.expander(f"Details: {activity['tool_name']}", expanded=False):
            st.caption(
                f"Started: {activity['started_at']}, duration: "
                f"{format_decimal(activity['duration_ms'], 0)} ms, status: {activity['status']}."
            )
            label("Input")
            st.json(display_prose(activity["tool_input"]))
            if activity.get("output") is not None:
                label("Tool output")
                st.json(display_prose(activity["output"]), expanded=False)
    st.caption("Evidence text uses display punctuation, raw records are unchanged.")


def _simulation_metadata(activities: list[dict[str, Any]]) -> None:
    meta = extract_simulation_metadata(activities)
    if meta is None:
        return
    section_header(
        "Simulation metadata",
        "Values are taken from the simulation tool output. The model is illustrative and uses synthetic data.",
        index="04",
    )
    columns = st.columns(4, gap="large")
    columns[0].metric("λ (incidents per year)", format_decimal(meta["lambda_used"]))
    columns[1].metric("μ", format_decimal(meta["severity_mu"], 3))
    columns[2].metric("σ", format_decimal(meta["severity_sigma"], 3))
    columns[3].metric("Simulations / seed", f"{meta['number_of_simulations']:,} / {meta['random_seed']}")
    st.caption(
        "λ (lambda) is the expected annual incident count, μ (mu) is the mean of log-losses, "
        "and σ (sigma) is their standard deviation."
    )
    st.caption(LOSS_UNIT_NOTICE)
    st.caption(f"λ source: {meta['lambda_source']}. Severity fitted to {meta['severity_losses_used']} losses "
               f"(data source: {meta['severity_data_source']}).")
    spacer()
    rows = [{"Metric": metric_label, "Baseline": format_amount(meta["baseline_metrics"][key]),
             **({"Stress": format_amount(meta["stress_metrics"][key])} if meta["stress_metrics"] else {})}
            for key, metric_label in METRIC_LABELS]
    st.dataframe(rows, hide_index=True, width="stretch")
