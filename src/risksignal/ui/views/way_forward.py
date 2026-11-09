"""Practical next steps for an approved, analyst-reviewed real-data pilot."""

import streamlit as st


def render_way_forward() -> None:
    st.title("Way Forward")
    st.write("From a synthetic demonstration to a useful tool tested on one real Operational Risk task.")

    st.subheader("1. Agree one real task with risk experts")
    st.write(
        "Choose a narrow question, such as reviewing recurring payment-system incidents and preparing "
        "evidence-backed follow-up questions."
    )

    st.subheader("2. Obtain approved real bank data")

    st.subheader("3. Review regulations and internal rules")
    st.write(
        "Ask the bank's compliance, legal, information-security and model-risk teams which requirements apply "
        "to its jurisdiction and use case. Agree privacy, confidentiality, data retention, access rights, "
        "third-party/LLM approval, model governance and operational-resilience controls before connecting data."
    )
    st.caption(
        "This prototype is not a compliance assessment or a regulatory capital engine. "
        "Applicable requirements must be confirmed by the institution's specialists."
    )

    st.subheader("4. Fit and test a real-data loss model")
    st.write(
        "Estimate incident frequency and loss severity from the approved history, then check whether the "
        "model's assumptions fit the data. Monte Carlo samples possible annual losses from that fitted model. "
        "Simulation alone does not make a reliable predictor."
    )
    st.write(
        "To assess real predictions, fit on earlier records and test on later records kept out of fitting. "
        "Compare against simple baselines, check calibration and uncertainty, and obtain independent review. "
        "The target is a probabilistic annual-loss range, not the exact date or cost of the next incident."
    )

    st.subheader("5. Create a live LLM")
    st.write(
        "Use an approved live LLM with read-only tools. On reviewed cases, compare its draft with the current "
        "analyst workflow. Measure source correctness, important evidence missed, unsupported statements, "
        "usefulness of next questions and review time. Keep case selection and assessment criteria agreed in advance."
    )
    st.write(
        "Every answer stays a draft: an experienced analyst checks the evidence and decides the follow-up. "
        "Start with a small supervised pilot and expand only if it improves the task without reducing quality."
    )

    st.subheader("Disclaimer and credits")
    st.caption(
        "Synthetic Atlas Bank data. The offline provider follows a script, not live LLM reasoning. "
        "This prototype is not a compliance assessment or a regulatory capital engine. "
        "Live LLM quality and real-data predictive performance have not been evaluated."
    )
    st.caption("Credits: Hadi Saad.")
