"""Unified AI investigation page and reusable conversational preview."""

from html import escape
from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    LLM_HELP,
    call_api,
    get_api_client,
    html,
    is_structured,
    label,
    render_answer,
    section_header,
)
from risksignal.ui.formatting import LOSS_UNIT_NOTICE, display_prose, format_decimal
from risksignal.ui.views.investigation import render_investigation
from risksignal.text import normalize_prose

HISTORY_KEY = "assistant_history"
PENDING_KEY = "assistant_pending"
MAX_SENT_TURNS = 20
STARTERS = (
    "Which systems should I look at first?",
    "What incidents did PAYMENT_ENGINE_01 have recently?",
    "What happens to CORE_LEDGER_01 under a shared vendor outage?",
    "Explain Expected Shortfall in plain words.",
)


def render_assistant() -> None:
    st.title("Risk Investigator")
    st.caption("AI Operational Risk Investigator")
    st.write("Investigate operational risk signals across incidents, controls, indicators and system dependencies.")
    st.caption("Research prototype. Synthetic Atlas Bank data only. The analyst makes the decision.")
    client = get_api_client()
    health = st.session_state.get("app_health") or call_api(client.health)
    if health is not None:
        if not health["llm_configured"]:
            st.info(f"The language-model provider is not configured. {LLM_HELP}")
        elif health["llm_provider"] == "mock":
            st.caption("Scripted offline provider, not live LLM tool calling.")
        else:
            st.caption("Live LLM provider active. Tool calls retrieve evidence only. They do not modify records.")

    with st.container(key="rs_investigator"):
        render_investigation(client)


# --------------------------------------------------------------------------- chat (in development)


def render_chat(client: ApiClient) -> None:
    section_header(
        "Ask RiskSignal",
        "A conversational assistant being built on the same tools: ask about a system, the whole portfolio or "
        "a method, and follow up in plain language. It works on the synthetic data but is not finished.",
        tag="In development",
    )
    st.caption(LOSS_UNIT_NOTICE)
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
             f'<p>{escape(normalize_prose(turn["content"]))}</p></div>')
        return
    with st.container(key=f"rs_chat_answer_{number}"):
        label("RiskSignal")
        if is_structured(turn["content"]):
            render_answer(turn["content"], key=f"rs_sections_chat_{number}")
        else:
            st.markdown(normalize_prose(turn["content"]))
        for warning in turn.get("warnings", []):
            st.warning(normalize_prose(warning))
        _evidence(turn)


def _evidence(turn: dict[str, Any]) -> None:
    activities = turn.get("tool_activity", [])
    if not activities:
        return
    count = len(activities)
    with st.expander(f"Evidence · {count} tool call{'s' if count != 1 else ''}"):
        for activity in activities:
            st.markdown(normalize_prose(f"**{activity['step']}. {activity['status'].capitalize()}:** {activity['summary']}"))
            st.caption(f"{activity['tool_name']} · {format_decimal(activity['duration_ms'], 0)} ms · "
                       f"input {display_prose(activity['tool_input'])}")
            if activity.get("output") is not None:
                st.json(display_prose(activity["output"]), expanded=False)
        st.caption("Evidence text uses display punctuation, raw records are unchanged.")
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
