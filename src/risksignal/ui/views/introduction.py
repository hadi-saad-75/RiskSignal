"""Presentation-style introduction to the RiskSignal demonstration."""

from pathlib import Path
from typing import Any

import streamlit as st

from risksignal.ui.components import banner, eyebrow, lead, ruled_list, section_header
from risksignal.ui.formatting import LOSS_UNIT_NOTICE

WALKTHROUGH = Path(__file__).resolve().parents[4] / "docs" / "media" / "risksignal_vscode_walkthrough.gif"


def render_introduction(pages: dict[str, Any]) -> None:
    banner()
    copy, visual = st.columns([5, 7], gap="large", vertical_alignment="center")
    with copy:
        eyebrow("01", "The idea")
        st.title("Operational risk, connected.")
        lead(
            "Incidents, key risk indicators, controls and technology dependencies often sit in separate places. "
            "RiskSignal brings them into one investigation so an analyst can see the evidence in context."
        )
        st.markdown(
            "**The goal:** connect the signals, quantify explicit assumptions and help an analyst decide "
            "what to investigate next."
        )
        st.caption("Demo data: fictional Atlas Bank · 20 systems · 10 processes · 8 vendors · 40 controls")
        st.page_link(
            pages["Overview"],
            label="Start the live demo",
            icon=":material/arrow_forward:",
        )
        st.caption(
            "Present from left to right: Overview, System Explorer, Scenario Analysis, Assistant, "
            "then Way forward: AI assistant."
        )
    with visual:
        st.image(
            str(WALKTHROUGH),
            width="stretch",
            alt=(
                "A three-part workflow: separate incident, KRI, control and dependency evidence is brought "
                "together by an investigation agent, then connected to a simulated loss distribution."
            ),
        )
        st.caption(
            "A visual summary of the workflow on the synthetic demo data. The animation illustrates a "
            "constructed example, not a real-world finding."
        )

    section_header(
        "A short, analyst-led walkthrough",
        "One fictional payment system provides a concrete thread through the evidence, dependency map and model.",
        index="02",
    )
    ruled_list([
        ("Gather evidence", "Review incidents, KRI trends and control-review status for one system."),
        ("Connect exposure", "Trace shared vendors and related systems, a connection is a lead, not causation."),
        ("Explore assumptions", "Compare a baseline with a clearly stated stress scenario, not a forecast."),
    ])

    section_header(
        "How Atlas Bank was built",
        "A fictional banking environment, created in Python to exercise the workflow without confidential data.",
        index="03",
    )
    structure, generation = st.columns(2, gap="large")
    with structure:
        ruled_list([
            ("1. Define a small banking ecosystem",
             "Write the systems, business processes and vendors by hand, then connect systems to their "
             "processes, external vendors and other systems. Add a control inventory and review dates."),
            ("2. Generate five years of observations",
             "Use seeded random draws for background incident counts, dates, categories and financial losses. "
             "Background counts use Poisson draws and losses use Lognormal draws. "
             "Generate monthly KRIs with noise and selected trends from October 2021 to September 2026."),
        ])
    with generation:
        ruled_list([
            ("3. Construct a readable payment-system example",
             "Add recent deployment and vendor incidents, an overdue regression-testing review and a vendor "
             "shared by the two payment engines. Other systems also have overdue controls or drifting indicators. "
             "These relationships are designed examples, not discoveries."),
            ("4. Validate, save and reproduce",
             "Check identifiers, references, dates and non-negative values, then save readable CSV tables "
             "and a SQLite database. The default random seed is 42, making the same dataset reproducible."),
        ])
    st.caption(LOSS_UNIT_NOTICE)
    st.caption(
        "The KRIs have no planted link to future incidents. Fitting a Lognormal to losses generated from "
        "Lognormal distributions does not establish that real bank losses follow that model."
    )

    section_header(
        "How RiskSignal was engineered",
        "The implementation path through the codebase, from the data foundation to a demonstrable application.",
        index="04",
    )
    ruled_list([
        ("1. Define the scope and domain",
         "Specify the analyst questions, data entities and research boundaries before building the demonstration."),
        ("2. Build the synthetic data foundation",
         "Implement typed data schemas, a seeded generator, integrity checks and CSV plus SQLite storage."),
        ("3. Implement and test the mathematical core",
         "Estimate incident frequency and severity, simulate annual aggregate losses, calculate tail metrics "
         "and compare baseline with stress using common random numbers."),
        ("4. Add dependency reasoning and deterministic tools",
         "Build a NetworkX graph and typed, read-only tools for retrieving evidence and running the model."),
        ("5. Connect the investigation agent",
         "Expose only the approved tools to the model, record its tool calls and check reported numbers "
         "against tool results. Provide an offline scripted provider for repeatable tests."),
        ("6. Expose, present and verify",
         "Wrap the tools in FastAPI, build the Streamlit interface, test the layers and document "
         "the model, limitations and deployment setup. Docker packaging is provided, not claimed as runtime-verified."),
    ])

    st.info(
        "**What this is:** a research prototype demonstrating an investigation workflow. "
        "**What it is not:** a validated model, a prediction, or a production decision tool. "
        "All Atlas Bank data are synthetic, the model assumptions are illustrative."
    )

    overview, explorer, scenario = st.columns(3, gap="large")
    with overview:
        st.page_link(pages["Overview"], label="Portfolio overview", icon=":material/space_dashboard:")
    with explorer:
        st.page_link(pages["System Explorer"], label="System evidence", icon=":material/account_tree:")
    with scenario:
        st.page_link(pages["Scenario Analysis"], label="Scenario analysis", icon=":material/monitoring:")
