"""Scenario analysis page."""

from typing import Any

import streamlit as st

from risksignal.ui.charts import distribution_figure
from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    call_api,
    credits_footer,
    get_api_client,
    section_header,
    simulation_notice,
    spacer,
    system_selector,
)
from risksignal.ui.formatting import (
    LOSS_UNIT_NOTICE,
    comparison_rows,
    format_amount,
    format_decimal,
)
from risksignal.text import normalize_prose

LAMBDA_SOURCES = {
    "system_history": "estimated from this system's own incident history",
    "bank_wide_per_system_average": "bank-wide average per system (this system has too few incidents)",
    "user_override": "user-supplied assumption",
}
SEVERITY_SOURCES = {"system": "this system's own losses", "category": "bank-wide losses of one category",
                    "bank_wide": "all bank-wide losses"}


def render_scenario_lab() -> None:
    with st.container(key="rs_scenario"):
        _render_scenario_lab()


def _render_scenario_lab() -> None:
    st.title("Scenario Analysis")
    st.write("Compare possible annual losses under baseline and stress assumptions.")
    simulation_notice()
    st.caption(LOSS_UNIT_NOTICE)
    client = get_api_client()
    system_id = system_selector(client, "lab")
    if system_id is None:
        credits_footer()
        return
    if "lab_scenarios" not in st.session_state:
        scenarios = call_api(client.scenarios)
        if scenarios is None:
            credits_footer()
            return
        st.session_state["lab_scenarios"] = scenarios
    scenarios = st.session_state["lab_scenarios"]
    if not scenarios["scenarios"]:
        st.error("No stress scenarios are available.")
        credits_footer()
        return
    settings = _inputs(scenarios["scenarios"])

    spacer()
    if st.button("Run baseline and stress comparison", type="primary"):
        st.session_state.pop("lab_result", None)
        st.session_state.pop("lab_result_settings", None)
        with st.spinner("Running the Monte Carlo simulation..."):
            result = _run(client, system_id, settings)
        if result is not None:
            st.session_state["lab_result"] = result
            st.session_state["lab_result_settings"] = settings
    result = st.session_state.get("lab_result")
    if result and result["system_id"] == system_id:
        if settings != st.session_state.get("lab_result_settings"):
            st.warning("Settings have changed. These results are from the previous run; run again to update them.")
        _results(result)
    else:
        st.caption("Set the simulation parameters and run the analysis to view the results.")
    credits_footer()


def _estimated_baseline(baseline: dict[str, Any]) -> None:
    assumptions, basis = baseline["model_assumptions"], baseline["observed_basis"]
    section_header(
        "Baseline parameter estimates",
        f"λ is {LAMBDA_SOURCES.get(assumptions['lambda_source'], assumptions['lambda_source'])}: "
        f"{basis['observed_incident_count']} incidents over {format_decimal(basis['observation_years'])} years. "
        f"μ and σ are fitted to {basis['severity_losses_used']} positive losses "
        f"({SEVERITY_SOURCES.get(basis['severity_data_source'], basis['severity_data_source'])}).",
        index="01",
    )
    columns = st.columns(3, gap="large")
    columns[0].metric("λ: expected incidents per year", format_decimal(assumptions["lambda_used"]))
    columns[1].metric("μ: log-severity location", format_decimal(assumptions["severity_mu"], 3))
    columns[2].metric("σ: log-severity spread", format_decimal(assumptions["severity_sigma"], 3))
    for note in basis["severity_fallback_notes"]:
        st.caption(normalize_prose(f"Fallback: {note}"))


def _inputs(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [s["scenario_id"] for s in scenarios]
    by_id = {s["scenario_id"]: s for s in scenarios}
    scenario_column, assumptions_column = st.columns(2, gap="medium")
    with scenario_column:
        scenario_id = st.selectbox("Stress scenario", ids, format_func=lambda i: by_id[i]["name"])
        st.caption("An illustrative what-if, not a forecast.")
    scenario = by_id[scenario_id]
    with assumptions_column:
        with st.expander("Advanced assumptions"):
            left, right = st.columns(2)
            n = left.number_input(
                "Number of simulations", min_value=1_000, max_value=1_000_000, value=100_000, step=10_000,
            )
            seed = right.number_input("Random seed", min_value=0, max_value=2**32 - 1, value=42, step=1)

            st.markdown(normalize_prose("\n".join(f"- {note}" for note in scenario["assumption_notes"])))
            use_custom = st.checkbox("Specify custom assumptions")
            left, right = st.columns(2)
            lam = left.number_input(
                "λ multiplier", min_value=0.1, max_value=100.0, value=1.5, step=0.1, disabled=not use_custom,
            )
            sigma = right.number_input(
                "σ multiplier", min_value=0.1, max_value=5.0, value=1.2, step=0.1, disabled=not use_custom,
            )
            st.caption("Custom assumptions are user-supplied and not calibrated.")
    return {"n": int(n), "seed": int(seed), "scenario_id": scenario_id, "use_custom": use_custom,
            "lambda_multiplier": float(lam), "sigma_multiplier": float(sigma)}


def _run(client: ApiClient, system_id: str, s: dict[str, Any]) -> dict[str, Any] | None:
    if s["use_custom"]:
        return call_api(client.compare_custom, system_id, s["lambda_multiplier"], s["sigma_multiplier"], s["n"], s["seed"])
    return call_api(client.compare, system_id, s["scenario_id"], s["n"], s["seed"])


def _results(result: dict[str, Any]) -> None:
    out = result["simulation_results"]
    stress = result["stress_assumptions"]
    base_assumptions = result["baseline_assumptions"]
    st.subheader("Baseline and stress compared")
    st.caption(normalize_prose(stress["label"]))
    rows = comparison_rows(out)
    st.dataframe([row for row in rows if row["Metric"] in
                  ("Mean annual loss", "P95", "Expected Shortfall 95%")],
                 hide_index=True, alt="Mean, 95th percentile and tail-average annual losses")
    distribution_column, details_column = st.columns(2, gap="medium")
    with distribution_column:
        with st.expander("Loss distribution", key="lab_distribution", on_change="rerun") as panel:
            if panel.open:
                st.plotly_chart(
                    distribution_figure(out["baseline_histogram"], out["baseline_metrics"]["p95"],
                                        out["stress_histogram"], out["stress_metrics"]["p95"]),
                    width="stretch", key="loss_distribution", theme=None,
                    alt="Baseline and stress simulated annual-loss distributions",
                )
    with details_column:
        with st.expander("Model details and all results"):
            _estimated_baseline({
                "model_assumptions": base_assumptions, "observed_basis": result["observed_basis"],
            })
            st.dataframe(rows, hide_index=True, alt="All annual-loss metrics")
            parameters = stress["stress_parameters"]
            st.table([
                {"Parameter": "λ (incidents per year)", "Baseline": format_decimal(base_assumptions["lambda_used"], 3),
                 "Stress": format_decimal(parameters["lambda_value"], 3)},
                {"Parameter": "μ", "Baseline": format_decimal(base_assumptions["severity_mu"], 3),
                 "Stress": format_decimal(parameters["mu"], 3)},
                {"Parameter": "σ", "Baseline": format_decimal(base_assumptions["severity_sigma"], 3),
                 "Stress": format_decimal(parameters["sigma"], 3)},
            ])
            st.caption(
                f"{result['baseline_assumptions']['number_of_simulations']:,} simulated years. "
                f"Random seed: {base_assumptions['random_seed']}."
            )
            st.markdown("**Assumptions and limits**")
            st.markdown(normalize_prose("\n".join(
                f"- {statement}" for statement in base_assumptions["assumption_statements"]
            )))
            st.markdown(normalize_prose("\n".join(
                f"- {note}" for note in stress["scenario"]["assumption_notes"]
            )))
    st.caption(normalize_prose(result["notice"]))
