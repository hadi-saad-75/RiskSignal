"""Unified, signal-led investigation workspace for one operational system.

The request goes to ``POST /agent/investigate``. The agent calls the deterministic tools, and the
page shows its findings before expandable monitoring, workpaper and model evidence.
"""

import re
from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    call_api,
    system_selector,
)
from risksignal.ui.formatting import split_sections
from risksignal.text import normalize_prose
from risksignal.ui.views.risk_workbench import (
    load_workpaper,
    monitoring_context,
    render_monitoring_snapshot,
    render_workbench_support,
)

STRESS_REQUEST = " Also compare the baseline with the SHARED_VENDOR_OUTAGE stress scenario."
RESPONSE_KEY = "agent_response"
RESPONSE_SYSTEM_KEY = "agent_response_system"
REQUEST_KEY = "agent_user_question"


def default_question(system_id: str) -> str:
    return (f"Investigate {system_id}. Review current monitoring signals, recent incidents, controls and "
            "dependencies. Summarise the evidence, explain what deserves attention, and suggest next steps.")


def render_investigation(client: ApiClient) -> None:
    controls, action = st.columns([5, 1], vertical_alignment="bottom")
    with controls:
        system_id = system_selector(client, "agent")
    if system_id is None:
        return
    with action:
        refresh = st.button("Refresh evidence", key="workbench_refresh", width="stretch")
    if refresh:
        st.session_state.pop(RESPONSE_KEY, None)
        st.session_state.pop(REQUEST_KEY, None)
        st.session_state.pop("system_inventory", None)
    workpaper = load_workpaper(client, system_id, refresh=refresh)
    if workpaper is None:
        return

    previous_system = st.session_state.get(RESPONSE_SYSTEM_KEY)
    if st.session_state.get(RESPONSE_KEY) and previous_system != system_id:
        st.session_state.pop(RESPONSE_KEY, None)
        st.session_state.pop(REQUEST_KEY, None)
    st.session_state[RESPONSE_SYSTEM_KEY] = system_id

    render_monitoring_snapshot(workpaper)
    with st.expander("Ask a specific question or include a stress scenario"):
        question = st.text_area(
            "What should the agent investigate?",
            value=default_question(system_id),
            key=f"agent_question_{system_id}",
            height=100,
        )
        include_stress = st.checkbox("Compare with the shared vendor outage scenario")
    run = st.button("Investigate system", type="primary", key="agent_investigate")

    if run:
        st.session_state.pop(RESPONSE_KEY, None)
        if not question.strip():
            st.error("Enter an investigation question before running. No investigation was started.")
            return
        text = question.strip() + (STRESS_REQUEST if include_stress else "")
        text = f"{text}\n\n{monitoring_context(workpaper)}"
        with st.spinner("Retrieving evidence and preparing the investigation summary..."):
            response = call_api(client.investigate, text)
        if response is not None:
            st.session_state[RESPONSE_KEY] = response
            st.session_state[REQUEST_KEY] = question.strip()

    response = st.session_state.get(RESPONSE_KEY)
    if response:
        _show(response, st.session_state.get(REQUEST_KEY, response["question"]))
    else:
        st.caption("The agent will connect the selected system's signals with incidents, controls, dependencies "
                   "and relevant quantitative evidence.")

    st.subheader("Supporting Evidence", anchor="supporting-evidence")
    render_workbench_support(client, workpaper, response if response else None)


def _show(response: dict[str, Any], user_question: str) -> None:
    st.caption(normalize_prose(f"Request: {user_question}"))
    if response["status"] != "completed":
        st.warning(f"The investigation did not complete normally (status: {response['status']}).")
    failures = [a for a in response["tool_activity"] if a["status"] != "completed"]
    for activity in failures:
        st.error(normalize_prose(f"Evidence retrieval failed: {activity['summary']}"))

    sections = split_sections(response["final_response"])
    expected = ("Investigation Summary", "Key Findings", "Next Investigations")
    bodies = {title: "\n".join(body for name, body in sections if name == title) for title in expected}
    for title, body in sections:
        if title == "Summary":
            st.warning(body)
    if not all(bodies.values()):
        st.warning("The agent did not return the expected investigation sections. "
                   "Review its complete response below. No formatted findings or priorities were extracted.")
    else:
        for title in expected:
            body = bodies[title]
            st.subheader(title)
            if title == "Investigation Summary":
                sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", body)
                st.markdown(" ".join(sentences[:3]))
                if len(sentences) > 3:
                    st.caption("Summary shortened. The complete response is available below.")
            else:
                items = _bullets(body)
                for number, item in enumerate(items[:3], start=1):
                    st.markdown(f"**{number}.** {item.lstrip('-* ')}" if title == "Next Investigations" else item)
                if len(items) > 3:
                    st.caption("Showing three items. The complete response is available below.")
    with st.expander("Complete agent response and limitations"):
        st.markdown(normalize_prose(response["final_response"]))
    for warning in response["warnings"]:
        st.warning(normalize_prose(warning))

    provider = (
        "Deterministic scripted mock, not live LLM tool calling"
        if response["provider"] == "mock" else "Live LLM tool calling"
    )
    st.caption(normalize_prose(
        f"Provider: {provider}. Language-model calls: {response['llm_calls']}. {response['disclaimer']}"
    ))


def _bullets(body: str) -> list[str]:
    """Keep continuation lines with their bullet, without dropping source citations."""
    items: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line) or not items:
            items.append(re.sub(r"^\s*\d+[.)]\s+", "- ", line))
        else:
            items[-1] += "\n" + line
    return items
