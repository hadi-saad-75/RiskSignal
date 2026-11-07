"""Short, evidence-led introduction to the RiskSignal demonstration."""

from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiRequestError, ApiUnavailableError
from risksignal.ui.charts import dependency_figure
from risksignal.ui.components import (
    START_API_HELP,
    banner,
    eyebrow,
    get_api_client,
    label,
    lead,
    ruled_list,
    section_header,
    show_request_error,
)
from risksignal.ui.formatting import LOSS_UNIT_NOTICE, label_for

SAMPLE_SYSTEM = "PAYMENT_ENGINE_01"
MARKET_EXAMPLES = (
    "This mix also appears in public role descriptions. "
    "[A Man Group enterprise-risk analyst role](https://builtin.com/job/risk-analyst-enterprise-risk/7644567) "
    "mentions risk and control records, issue and vendor tracking, reports, and workflow improvement; it names "
    "Excel, Power BI and Power Automate. "
    "[A Bank of America risk-process role](https://careers.bankofamerica.com/en-us/job-detail/26027282/"
    "risk-process-analyst-multiple-locations-esomprank-y3ga2stumv-4) describes supporting process and control "
    "testing, analysis and reporting. These are examples, not a survey of every team."
)


def render_introduction(pages: dict[str, Any]) -> None:
    banner()
    eyebrow("01", "The work today")
    st.title("Operational risk, connected.")
    lead(
        "Analysts bring together information about incidents, indicators, controls and suppliers to understand "
        "what happened and what deserves a closer look."
    )
    st.write(
        "That work can include keeping risk and control records up to date, following issues through to closure, "
        "checking supplier information, reviewing indicator data, and preparing reports for managers. Some roles "
        "also ask for better dashboards and workflow automation."
    )
    st.markdown(MARKET_EXAMPLES)
    st.caption(
        "Job descriptions tell us what a role is responsible for, not how many hours each task takes or whether "
        "every team still relies on manual searches. This prototype does not claim that current work is slow or "
        "promise time savings. It asks a practical question: can connected evidence make an investigation easier "
        "to start and review?"
    )

    section_header(
        "The goal: move from a signal to supported next steps",
        "RiskSignal is a research prototype for helping an analyst find relevant evidence, not for making a risk decision.",
        index="02",
    )
    investigation, recommendations = st.columns(2, gap="large")
    with investigation, st.container(border=True):
        st.markdown(":material/search: **Objective 1 · Intelligent investigation**")
        st.subheader("Connect the evidence")
        st.write(
            "Start with a system or a risk signal. Bring together related incident, indicator, control and "
            "supplier records so the analyst can examine them in one place."
        )
    with recommendations, st.container(border=True):
        st.markdown(":material/fact_check: **Objective 2 · Evidence-backed recommendations**")
        st.subheader("Show why it matters")
        st.write(
            "Show which records support a finding and suggest a useful follow-up question. The analyst checks "
            "the evidence, adds context and decides what to do next."
        )

    section_header("A simple analyst workflow")
    ruled_list([
        ("1. Notice", "See a recent incident or indicator that may deserve attention."),
        ("2. Investigate", "Ask RiskSignal to retrieve and connect relevant records for that system."),
        ("3. Review", "Check the supporting sources and choose the next step as a human analyst."),
    ])

    section_header(
        "Atlas Bank: a small sample",
        "A fictional example of the information the prototype can bring together. All records shown are synthetic.",
        index="05",
    )
    _render_atlas_preview()
    st.caption(
        "Sample environment: 20 systems · 10 business processes · 8 suppliers · 40 controls · five years of "
        "synthetic observations. A shared connection is a reason to investigate, not proof of cause."
    )
    st.info(
        "**Research prototype:** no real bank data, no forecast and no production decision. "
        "Loss simulations use illustrative assumptions. The analyst remains responsible for conclusions."
    )
    st.caption(LOSS_UNIT_NOTICE)
    st.page_link(
        pages["System Explorer"],
        label="Start the live demo",
        icon=":material/arrow_forward:",
    )


def _render_atlas_preview() -> None:
    client = get_api_client()
    try:
        profile = client.profile(SAMPLE_SYSTEM)
        dependencies = client.dependencies(SAMPLE_SYSTEM)
        incidents = client.incidents(SAMPLE_SYSTEM, 12)
    except ApiUnavailableError as error:
        st.error(f"{error} {START_API_HELP}")
        return
    except ApiRequestError as error:
        show_request_error(error)
        return

    details, map_column = st.columns([5, 7], gap="large")
    with details, st.container(border=True):
        label("Sample system")
        st.subheader(profile["system"]["name"])
        st.caption(f"{profile['system']['system_id']} · {profile['system']['criticality']} criticality")
        st.markdown(f"**Business process**  \n{profile['primary_process']['name']}")
        st.caption(
            f"{profile['metadata']['total_incidents_recorded']} recorded incidents · "
            f"{profile['metadata']['number_of_controls']} recorded controls"
        )
        st.markdown("**Recent synthetic incidents**")
        for incident in incidents["incidents"][:2]:
            st.markdown(f"**{incident['date']} · {label_for(incident['category'])}**")
            st.write(incident["description"])

    with map_column:
        figure = dependency_figure(SAMPLE_SYSTEM, dependencies)
        figure.update_layout(
            title={"text": "Systems, suppliers and shared processes"},
            height=390,
            margin={"l": 8, "r": 8, "t": 64, "b": 12},
        )
        st.plotly_chart(
            figure,
            width="stretch",
            key="atlas_preview_map",
            theme=None,
            alt="A sample map of one system, its suppliers, business process and related systems",
        )
