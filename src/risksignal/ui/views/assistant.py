"""Assistant page: one place to ask RiskSignal anything and to run a full investigation.

This is an early version. The roadmap at the bottom of the page lists what it does not do yet.
"""

from html import escape
from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    LLM_HELP,
    banner,
    call_api,
    get_api_client,
    html,
    is_structured,
    label,
    page_header,
    render_answer,
    rule,
    ruled_list,
    section_header,
    spacer,
    system_selector,
)
from risksignal.ui.formatting import METRIC_LABELS, extract_simulation_metadata, format_amount, format_decimal

HISTORY_KEY = "assistant_history"
PENDING_KEY = "assistant_pending"
MAX_SENT_TURNS = 20
STRESS_REQUEST = " Also compare the baseline with the SHARED_VENDOR_OUTAGE stress scenario."
STARTERS = (
    "Which systems should I look at first?",
    "What incidents did PAYMENT_ENGINE_01 have recently?",
    "What happens to CORE_LEDGER_01 under a shared vendor outage?",
    "Explain Expected Shortfall in plain words.",
)
ROADMAP = (
    ("Evaluation with a live model",
     "A set of real operator questions with expected evidence, to measure tool choice, grounding and usefulness."),
    ("Institutional data",
     "Connectors to the incident, control and KRI systems of record instead of the synthetic Atlas Bank data."),
    ("Saved cases and audit trail",
     "Conversations and investigations stored as case files that a reviewer can reopen, comment on and sign off."),
    ("Wider analysis",
     "Trend tests, links between KRIs and later incidents, more scenarios, and search over policies and past reviews."),
    ("Access control and approved hosting",
     "Authentication, entitlements by business area, and a language model hosted under the bank's approval."),
    ("Analyst feedback",
     "Marking answers as useful or wrong, so that prompts and tools improve on real use."),
)


def default_question(system_id: str) -> str:
    return (f"Investigate {system_id}. Review recent incidents, KRIs, controls and dependencies, run a baseline "
            "loss simulation, and identify questions that an Operational Risk analyst should investigate.")


def render_assistant() -> None:
    banner()
    page_header(
        "01", "Assistant · early version", "Ask RiskSignal",
        "Ask anything about the systems, incidents, controls, vendors, loss simulations or the methods behind "
        "them, or run a full investigation of one system. Follow-up questions keep the context. Every figure "
        "comes from read-only tools, and the evidence behind each answer is listed under it.",
    )
    client = get_api_client()
    health = call_api(client.health)
    if health is not None and not health["llm_configured"]:
        st.info(f"The language-model provider is not configured. {LLM_HELP}")

    history: list[dict[str, Any]] = st.session_state.setdefault(HISTORY_KEY, [])
    typed = st.chat_input("Ask about a system, the portfolio or a method")
    requested = _investigation_controls(client)
    message = (typed or requested or st.session_state.pop(PENDING_KEY, None) or "").strip()

    if not history and not message:
        _starters()
    for number, turn in enumerate(history):
        _show_turn(number, turn)
    if message:
        _ask(client, history, message)
    if history:
        spacer()
        if st.button("Start a new conversation", key="assistant_reset"):
            st.session_state[HISTORY_KEY] = []
            st.rerun()
    _roadmap()


def _investigation_controls(client: ApiClient) -> str | None:
    """System picker and button that send a full investigation request into the conversation."""
    rule(subtle=True)
    spacer()
    picker, _, options = st.columns([5, 1, 6], vertical_alignment="bottom")
    with picker:
        system_id = system_selector(client, "assistant", label="Full investigation of")
    if system_id is None:
        return None
    with options:
        include_stress = st.checkbox("Include the SHARED_VENDOR_OUTAGE stress scenario", key="assistant_stress")
        clicked = st.button("Investigate this system", type="primary", key="assistant_investigate")
    return default_question(system_id) + (STRESS_REQUEST if include_stress else "") if clicked else None


def _starters() -> None:
    spacer()
    label("Or try asking")
    columns = st.columns(2)
    for index, question in enumerate(STARTERS):
        if columns[index % 2].button(question, key=f"assistant_starter_{index}", width="stretch"):
            st.session_state[PENDING_KEY] = question
            st.rerun()


def _show_turn(number: int, turn: dict[str, Any]) -> None:
    if turn["role"] == "user":
        html(f'<div class="rs-chat-question"><span class="rs-index">{number // 2 + 1:02d}</span>'
             f'<p>{escape(turn["content"])}</p></div>')
        return
    with st.container(key=f"rs_chat_answer_{number}"):
        label("RiskSignal")
        if is_structured(turn["content"]):
            render_answer(turn["content"], key=f"rs_sections_{number}")
        else:
            st.markdown(turn["content"])
        for warning in turn.get("warnings", []):
            st.warning(warning)
        _simulation_metadata(turn.get("tool_activity", []))
        _evidence(turn)


def _simulation_metadata(activities: list[dict[str, Any]]) -> None:
    meta = extract_simulation_metadata(activities)
    if meta is None:
        return
    spacer()
    label("Simulation metadata")
    columns = st.columns(4, gap="large")
    columns[0].metric("λ (incidents per year)", format_decimal(meta["lambda_used"]))
    columns[1].metric("μ", format_decimal(meta["severity_mu"], 3))
    columns[2].metric("σ", format_decimal(meta["severity_sigma"], 3))
    columns[3].metric("Simulations / seed", f"{meta['number_of_simulations']:,} / {meta['random_seed']}")
    st.caption(f"Read from the simulation tool output, not from the answer text. λ source: {meta['lambda_source']}. "
               f"Severity fitted to {meta['severity_losses_used']} losses (data source: {meta['severity_data_source']}).")
    st.dataframe(
        [{"Metric": name, "Baseline": format_amount(meta["baseline_metrics"][key]),
          **({"Stress": format_amount(meta["stress_metrics"][key])} if meta["stress_metrics"] else {})}
         for key, name in METRIC_LABELS],
        hide_index=True, width="stretch",
    )


def _evidence(turn: dict[str, Any]) -> None:
    activities = turn.get("tool_activity", [])
    if not activities:
        return
    count = len(activities)
    with st.expander(f"Evidence · {count} tool call{'s' if count != 1 else ''}"):
        for activity in activities:
            st.markdown(f"**{activity['step']}. {activity['status'].capitalize()}:** {activity['summary']}")
            st.caption(f"{activity['tool_name']} · {format_decimal(activity['duration_ms'], 0)} ms · "
                       f"input {activity['tool_input']}")
            if activity.get("output") is not None:
                st.json(activity["output"], expanded=False)
        st.caption(f"Provider: {turn.get('provider', 'unknown')}. Data are synthetic (fictional Atlas Bank).")


def _ask(client: ApiClient, history: list[dict[str, Any]], message: str) -> None:
    question = {"role": "user", "content": message}
    _show_turn(len(history), question)
    sent = [{"role": t["role"], "content": t["content"]} for t in history[-MAX_SENT_TURNS:]]
    with st.spinner("Checking the evidence..."):
        response = call_api(client.chat, message, sent, include_tool_outputs=True)
    if response is None:
        return
    answer = {
        "role": "assistant",
        "content": response["final_response"],
        "tool_activity": response["tool_activity"],
        "warnings": response["warnings"]
        + ([] if response["status"] == "completed" else [f"The answer did not complete normally ({response['status']})."]),
        "provider": response["provider"],
    }
    history.extend([question, answer])
    _show_turn(len(history) - 1, answer)


def _roadmap() -> None:
    section_header(
        "Not built yet",
        "This is an early version: it shows the approach on synthetic data. These are the next steps to make it "
        "an assistant an Operational Risk team could rely on.",
    )
    left, _, right = st.columns([6, 1, 6])
    with left:
        ruled_list(ROADMAP[:3])
    with right:
        ruled_list(ROADMAP[3:])
