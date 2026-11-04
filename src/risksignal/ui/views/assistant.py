"""Assistant page.

1. Investigation: the full, tool-based investigation of one system, as before.
2. Ask RiskSignal: the conversational assistant, shown as in development.
3. Way forward: what is planned next.
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
    ruled_list,
    section_header,
    spacer,
)
from risksignal.ui.formatting import format_decimal
from risksignal.ui.views.investigation import render_investigation

HISTORY_KEY = "assistant_history"
PENDING_KEY = "assistant_pending"
MAX_SENT_TURNS = 20
STARTERS = (
    "Which systems should I look at first?",
    "What incidents did PAYMENT_ENGINE_01 have recently?",
    "What happens to CORE_LEDGER_01 under a shared vendor outage?",
    "Explain Expected Shortfall in plain words.",
)
WAY_FORWARD = (
    ("Conversational assistant",
     "Finish the chat above: free questions over several turns, answers adapted to each question, and the "
     "same evidence rules as the investigation."),
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
)


def render_assistant() -> None:
    banner()
    page_header(
        "01", "Assistant", "RiskSignal Assistant",
        "A language model selects among deterministic tools for retrieving system profiles, incidents, key "
        "risk indicators, controls, dependencies, and simulation results. It summarises the returned evidence "
        "and may suggest questions for further review. The model cannot modify records or make risk decisions. "
        "Reported quantitative claims are checked against the tool outputs; unmatched values are flagged.",
        intro_below=True,
    )
    client = get_api_client()
    health = call_api(client.health)
    if health is not None and not health["llm_configured"]:
        st.info(f"The language-model provider is not configured. {LLM_HELP}")

    render_investigation(client)
    _chat(client)
    _way_forward()


# --------------------------------------------------------------------------- chat (in development)


def _chat(client: ApiClient) -> None:
    section_header(
        "Ask RiskSignal",
        "A conversational assistant being built on the same tools: ask about a system, the whole portfolio or "
        "a method, and follow up in plain language. It works on the synthetic data but is not finished.",
        tag="In development",
    )
    history: list[dict[str, Any]] = st.session_state.setdefault(HISTORY_KEY, [])
    conversation = st.container()
    with st.container(key="rs_chat_input_box"):  # inside a container the input stays in the section
        typed = st.chat_input("Ask about a system, the portfolio or a method")
    message = (typed or st.session_state.pop(PENDING_KEY, None) or "").strip()

    with conversation:
        if not history and not message:
            _starters()
        for number, turn in enumerate(history):
            _show_turn(number, turn)
        if message:
            _ask(client, history, message)
    if history and st.button("Start a new conversation", key="assistant_reset"):
        st.session_state[HISTORY_KEY] = []
        st.rerun()


def _starters() -> None:
    label("Try asking")
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
            render_answer(turn["content"], key=f"rs_sections_chat_{number}")
        else:
            st.markdown(turn["content"])
        for warning in turn.get("warnings", []):
            st.warning(warning)
        _evidence(turn)


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


# --------------------------------------------------------------------------- way forward


def _way_forward() -> None:
    section_header(
        "Way forward",
        "This is an early version that shows the approach on synthetic data. These are the next steps to make "
        "it an assistant an Operational Risk team could rely on.",
    )
    left, _, right = st.columns([6, 1, 6])
    with left:
        ruled_list(WAY_FORWARD[:3])
    with right:
        ruled_list(WAY_FORWARD[3:])
