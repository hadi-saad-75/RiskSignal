"""Practical next steps for an approved, analyst-reviewed real-data pilot."""

import streamlit as st


def render_way_forward() -> None:
    with st.container(key="rs_wf_hero"):
        st.title("Way Forward")
        st.write("From a synthetic demonstration to a useful tool tested on one real Operational Risk task.")
        st.caption("Proposed work, not capabilities or results achieved today.")

    with st.container(border=True, key="rs_step_1"):
        st.subheader("1. Agree one real task with risk experts")
        st.write(
            "Work with Operational Risk analysts, system owners and model-validation specialists. "
            "Choose a narrow question, such as reviewing recurring payment-system incidents and preparing "
            "evidence-backed follow-up questions. Agree what a correct and useful answer looks like."
        )

    with st.container(border=True, key="rs_step_2"):
        st.subheader("2. Obtain approved real bank data")
        st.write(
            "With a bank partner's permission, use incident history, losses, KRIs, control-test results and "
            "system/vendor dependencies. Check missing records, dates, shared IDs, loss definitions, currencies "
            "and recoveries. Start with the minimum data needed, anonymised where appropriate."
        )
        st.caption("Data access is not assumed. Confidential records must not be uploaded to an unapproved LLM service.")

    with st.container(border=True, key="rs_step_3"):
        st.subheader("3. Review regulations and internal rules")
        st.write(
            "Ask the bank's compliance, legal, information-security and model-risk teams which requirements apply "
            "to its jurisdiction and use case. Agree privacy, confidentiality, data retention, access rights, "
            "third-party/LLM approval, model governance and operational-resilience controls before connecting data."
        )
        st.caption("This prototype is not a compliance assessment or a regulatory capital engine. "
                   "Applicable requirements must be confirmed by the institution's specialists.")

    with st.container(border=True, key="rs_step_4"):
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
        st.caption("Do not claim predictive validity unless the out-of-sample evidence supports it. "
                   "KRIs and dependencies do not automatically change today's loss model.")

    with st.container(border=True, key="rs_step_5"):
        st.subheader("5. Test the live LLM on the agreed analyst task")
        st.write(
            "Use an approved live LLM with read-only tools. On reviewed cases, compare its draft with the current "
            "analyst workflow. Measure source correctness, important evidence missed, unsupported statements, "
            "usefulness of next questions and review time. Keep case selection and assessment criteria agreed in advance."
        )
        st.write(
            "Every answer stays a draft: an experienced analyst checks the evidence and decides the follow-up. "
            "Start with a small supervised pilot and expand only if it improves the task without reducing quality."
        )

    with st.container(border=True, key="rs_wf_success"):
        st.subheader("What success would look like")
        st.write(
            "A reviewed investigation draft on a real task, with traceable sources, useful next questions and "
            "measured quality and time results. Separately, an independently assessed loss model with honest "
            "out-of-sample results, whether those results support prediction or show that more work is needed."
        )
    st.info("Today: synthetic data and a scripted offline demonstration. Live LLM quality, real-bank prediction "
            "performance and regulatory suitability remain unverified.")
