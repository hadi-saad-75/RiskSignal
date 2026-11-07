"""Scenario analysis page."""

from typing import Any

import streamlit as st

from risksignal.ui.charts import distribution_figure
from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import (
    call_api,
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
    st.title("Scenario Analysis")
    st.write("Compare possible annual losses under baseline and stress assumptions.")
    simulation_notice()
    st.caption(LOSS_UNIT_NOTICE)
    client = get_api_client()
    system_id = system_selector(client, "lab")
    if system_id is None:
        return
    if "lab_scenarios" not in st.session_state:
        scenarios = call_api(client.scenarios)
        if scenarios is None:
            return
        st.session_state["lab_scenarios"] = scenarios
    scenarios = st.session_state["lab_scenarios"]
    if not scenarios["scenarios"]:
        st.error("No stress scenarios are available.")
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
    st.markdown(
        "**λ (lambda)** is the expected number of incidents per year. "
        "**μ (mu)** is the mean of log-losses. "
        "**σ (sigma)** is the standard deviation of log-losses, not of annual loss. "
        "A larger σ gives a wider severity distribution at a fixed μ."
    )
    for note in basis["severity_fallback_notes"]:
        st.caption(normalize_prose(f"Fallback: {note}"))
    spacer()
    with st.container():
        st.markdown(
            "The model counts incidents per year with a **Poisson** distribution, `N ~ Poisson(λ)`, where **λ** is the "
            "expected number of incidents per year. The loss of each incident follows a **Lognormal** distribution, "
            "`X ~ Lognormal(μ, σ)`: its logarithm is bell-shaped with mean **μ** and standard deviation **σ**. So `exp(μ)` "
            "is the median loss of one incident, and a larger **σ** means a heavier tail of rare, very large losses. "
            "The annual loss is `L = X₁ + … + X_N`, simulated many times. The parameters are estimated from the "
            "synthetic history, the synthetic losses were themselves generated from Lognormal distributions, so a good "
            "fit says nothing about real losses."
        )


def _inputs(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [s["scenario_id"] for s in scenarios]
    by_id = {s["scenario_id"]: s for s in scenarios}
    scenario_id = st.selectbox("Stress scenario", ids, format_func=lambda i: by_id[i]["name"])
    scenario = by_id[scenario_id]
    st.caption("An illustrative what-if, not a forecast.")
    with st.expander("Advanced assumptions"):
        left, right = st.columns(2)
        n = left.number_input("Number of simulations", min_value=1_000, max_value=1_000_000, value=100_000, step=10_000)
        seed = right.number_input("Random seed", min_value=0, max_value=2**32 - 1, value=42, step=1)

        st.markdown(normalize_prose("\n".join(f"- {note}" for note in scenario["assumption_notes"])))
        use_custom = st.checkbox("Specify custom assumptions")
        left, right = st.columns(2)
        lam = left.number_input(
            "λ multiplier", min_value=0.1, max_value=100.0, value=1.5, step=0.1, disabled=not use_custom,
            help="Multiplies the baseline incident rate. A value of 1.5 means 50% more expected incidents per year.",
        )
        sigma = right.number_input(
            "σ multiplier", min_value=0.1, max_value=5.0, value=1.2, step=0.1, disabled=not use_custom,
            help="Multiplies the standard deviation of log-losses. A value of 1.2 means 20% more log-loss spread.",
        )
        st.markdown(
            "A λ multiplier of **1.5** increases the expected incident rate by **50%**. "
            "A σ multiplier of **1.2** increases log-loss spread by **20%**, not every loss by 20%. "
            "The median incident loss stays unchanged when only σ changes, but the mean and upper tail change."
        )
        st.caption(
            "These user-specified assumptions are not estimated or calibrated. They are not available "
            "to the language-model investigation function."
        )
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
    st.caption("95th percentile: 95% of simulated annual losses are at or below this amount. "
               "Expected Shortfall 95%: average of the worst 5% of simulated years.")
    with st.expander("Loss distribution", key="lab_distribution", on_change="rerun") as panel:
        if panel.open:
            st.plotly_chart(
                distribution_figure(out["baseline_histogram"], out["baseline_metrics"]["p95"],
                                    out["stress_histogram"], out["stress_metrics"]["p95"]),
                width="stretch", key="loss_distribution", theme=None,
                alt="Baseline and stress simulated annual-loss distributions",
            )
    with st.expander("Model details and all results"):
        _estimated_baseline({"model_assumptions": base_assumptions, "observed_basis": result["observed_basis"]})
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
        f"{result['baseline_assumptions']['number_of_simulations']:,} simulated years, seed {base_assumptions['random_seed']}, "
        "same seed and common random numbers for baseline and stress. Closed-form mean as a check: "
        f"baseline {format_amount(out['baseline_analytic_mean_annual_loss'])}, "
        f"stress {format_amount(out['stress_analytic_mean_annual_loss'])}."
        )
        st.markdown(normalize_prose("\n".join(f"- {s}" for s in base_assumptions["assumption_statements"])))
        st.markdown(normalize_prose("\n".join(f"- {note}" for note in stress["scenario"]["assumption_notes"])))
    st.caption(normalize_prose(result["notice"]))
