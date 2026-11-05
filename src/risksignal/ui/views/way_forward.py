"""Limitations, research directions and the conversational assistant preview."""

import streamlit as st

from risksignal.ui.components import (
    LLM_HELP,
    banner,
    call_api,
    get_api_client,
    page_header,
    ruled_list,
    section_header,
)
from risksignal.ui.views.assistant import render_chat


def render_way_forward() -> None:
    banner()
    page_header(
        "06", "Research directions", "Way forward: AI assistant",
        "From evidence and investigation questions to a more informed assistant. "
        "The ideas below are future work, not capabilities or results claimed by this prototype.",
    )
    section_header(
        "What the prototype cannot establish",
        "Working code and reproducible calculations are not the same as a validated risk model.",
    )
    ruled_list([
        ("Constructed evidence, not real-bank findings",
         "Atlas Bank is fictional. Its payment-system story was deliberately built into the data, "
         "and its losses were generated from Lognormal distributions. A good fit is not real-world validation."),
        ("Simplified loss model",
         "The baseline assumes constant Poisson frequency and independent Lognormal losses. Small samples and "
         "parameter uncertainty limit the results. Controls and KRIs are evidence, not predictors in this model. "
         "The graph exposes connections but does not simulate joint vendor failures or contagion."),
        ("Investigation support, not institutional expertise",
         "The current agent assembles evidence and mostly suggests investigation questions. It has no bank-specific "
         "policy knowledge or expert judgement. Its number checks are best effort and do not verify every claim."),
        ("Not ready for operational decisions",
         "There is no predictive validation, regulatory capital claim, persistent case audit trail or production "
         "access control. The live-model path still needs evaluation. The offline provider is a script, not an LLM."),
    ])

    section_header(
        "Two foundations for the next stage",
        "Mathematical assumptions and institutional calibration must be examined together with risk specialists.",
    )
    maths, calibration = st.columns(2, gap="large")
    with maths:
        st.subheader("Mathematical assumptions")
        ruled_list([
            ("Is Poisson appropriate?",
             "Test whether counts are independent and stable, and whether their variance exceeds their mean."),
            ("Negative Binomial and time-varying intensity",
             "Compare a Negative Binomial for overdispersion and a rate λ(t) that changes over time "
             "against the simple Poisson baseline, using out-of-sample evidence."),
            ("Tails, dependence and uncertainty",
             "Investigate severity tails, joint vendor events and parameter uncertainty only when enough "
             "relevant data are available."),
            ("Separate regulatory capital from research",
             "If capital is the intended use, consult regulatory specialists on the applicable Basel standardised "
             "approach. It is not a replacement probability distribution or an implemented feature here."),
        ])
    with calibration:
        st.subheader("Institutional calibration")
        ruled_list([
            ("Real incidents and loss history",
             "Agree loss definitions, currency, recoveries, observation windows and data quality. "
             "Use approved real KRIs and control records."),
            ("Verified system and vendor dependencies",
             "Replace the fictional graph with maintained maps of systems, business services and external vendors."),
            ("Institution-specific scenarios",
             "Design and justify stress assumptions with domain experts rather than reuse demonstration multipliers."),
            ("Backtesting and validation",
             "Set the intended use and evaluation criteria first, then test stability, sensitivity and out-of-sample "
             "performance with independent review and model governance."),
        ])

    section_header(
        "From suggested questions to informed draft answers",
        "Expert decisions would be reference evidence, not authority delegated to the agent. "
        "A human analyst would still review and decide.",
    )
    now, future = st.columns(2, gap="large")
    with now:
        st.subheader("Now")
        for index, step in enumerate(("Evidence", "Tool-based agent", "Suggested investigation questions")):
            if index:
                st.markdown("↓")
            with st.container(border=True):
                st.markdown(f"**{step}**")
        st.write(
            "The agent can highlight an overdue control or shared vendor and suggest what to examine. "
            "It cannot know whether a control is effective or why an incident occurred."
        )
    with future:
        st.subheader("Proposed next step")
        for index, step in enumerate((
            "Evidence",
            "Approved resolved cases, control documentation and past investigations",
            "Documented expert decisions",
            "Retrieval-assisted agent",
            "Cited draft answer and human review",
        )):
            if index:
                st.markdown("↓")
            with st.container(border=True):
                st.markdown(f"**{step}**")
        st.write(
            "Use institution-approved knowledge and source citations to draft more useful answers. "
            "Evaluate incorrect answers, missing evidence, usefulness and analyst time before wider use."
        )

    section_header(
        "Could a multi-agent design help?",
        "A potentially useful research direction, not a proven improvement and not implemented.",
    )
    ruled_list([
        ("Specialist roles",
         "An evidence agent could retrieve approved sources, a graph agent could examine shared exposures, "
         "a quantitative agent could call the simulation tools, and a control agent could review control evidence."),
        ("Coordination and review",
         "A lead agent could assemble a cited draft, with a separate evidence-checking role. "
         "All roles would use restricted tools and a shared case record, with a human retaining final judgement."),
        ("Prove the benefit before adding complexity",
         "Compare against the existing single-agent workflow on the same tasks. Measure evidence coverage, errors, "
         "analyst usefulness, latency and cost. More agents can repeat the same errors and increase overhead."),
    ])

    section_header("Practical development roadmap", "A proposed sequence for a governed pilot, not completed work.")
    ruled_list([
        ("1. Agree the use case and approved data",
         "Define the analyst task, data access, success criteria and decision boundaries."),
        ("2. Calibrate and validate a transparent baseline",
         "Assess the mathematical assumptions and design scenarios with the institution."),
        ("3. Add approved knowledge and evaluate the assistant",
         "Test retrieval, citations, tool choice and answer quality against reviewed reference cases."),
        ("4. Compare specialist agents where justified",
         "Keep a multi-agent design only if it improves the measured outcome over the simpler baseline."),
        ("5. Add operational controls",
         "Saved cases, audit trails, analyst feedback, authentication, entitlements and approved hosting."),
    ])

    client = get_api_client()
    section_header(
        "Conversational preview",
        "An unfinished preview using the existing synthetic-data tools. "
        "It does not implement the institutional knowledge or multi-agent design described above.",
    )
    health = call_api(client.health)
    if health is not None:
        if not health["llm_configured"]:
            st.info(f"The language-model provider is not configured. {LLM_HELP}")
        elif health["llm_provider"] == "mock":
            st.info("Offline mock provider, answers are scripted from tool results, not generated by a live language model.")
    render_chat(client)
