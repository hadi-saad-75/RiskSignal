"""Assistant page: a conversation with RiskSignal about the systems, the portfolio and the methods."""

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
    label,
    page_header,
    spacer,
)

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
    banner()
    page_header(
        "02", "Assistant", "Ask RiskSignal",
        "Ask anything about the systems, incidents, controls, vendors, loss simulations or the methods behind "
        "them. Follow-up questions keep the context. Every figure comes from read-only tools, and the evidence "
        "behind each answer is listed under it.",
    )
    client = get_api_client()
    health = call_api(client.health)
    if health is not None and not health["llm_configured"]:
        st.info(f"The language-model provider is not configured. {LLM_HELP}")

    history: list[dict[str, Any]] = st.session_state.setdefault(HISTORY_KEY, [])
    typed = st.chat_input("Ask about a system, the portfolio or a method")
    message = (typed or st.session_state.pop(PENDING_KEY, None) or "").strip()

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


def _starters() -> None:
    label("Try asking")
    columns = st.columns(2)
    for index, question in enumerate(STARTERS):
        if columns[index % 2].button(question, key=f"assistant_starter_{index}", width="stretch"):
            st.session_state[PENDING_KEY] = question
            st.rerun()


def _show_turn(number: int, turn: dict[str, Any]) -> None:
    if turn["role"] == "user":
        exchange = number // 2 + 1
        html(f'<div class="rs-chat-question"><span class="rs-index">{exchange:02d}</span>'
             f'<p>{escape(turn["content"])}</p></div>')
        return
    with st.container(key=f"rs_chat_answer_{number}"):
        label("RiskSignal")
        st.markdown(turn["content"])
        for warning in turn.get("warnings", []):
            st.warning(warning)
        activity = turn.get("activity", [])
        if activity:
            with st.expander(f"Evidence · {len(activity)} tool call{'s' if len(activity) != 1 else ''}"):
                for line in activity:
                    st.markdown(f"- {line}")
                st.caption(f"Provider: {turn.get('provider', 'unknown')}. Data are synthetic (fictional Atlas Bank).")


def _ask(client: ApiClient, history: list[dict[str, Any]], message: str) -> None:
    question = {"role": "user", "content": message}
    _show_turn(len(history), question)
    sent = [{"role": t["role"], "content": t["content"]} for t in history[-MAX_SENT_TURNS:]]
    with st.spinner("Checking the evidence..."):
        response = call_api(client.chat, message, sent)
    if response is None:
        return
    answer = {
        "role": "assistant",
        "content": response["final_response"],
        "activity": response["activity_log"],
        "warnings": response["warnings"]
        + ([] if response["status"] == "completed" else [f"The answer did not complete normally ({response['status']})."]),
        "provider": response["provider"],
    }
    history.extend([question, answer])
    _show_turn(len(history) - 1, answer)
