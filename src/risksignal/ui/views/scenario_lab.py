"""Page 3: Scenario Lab."""

from typing import Any

import streamlit as st

from risksignal.ui.charts import distribution_figure
from risksignal.ui.components import banner, call_api, get_api_client, simulation_notice, system_selector
from risksignal.ui.formatting import (
    METRIC_LABELS,
    comparison_rows,
    format_amount,
    format_decimal,
    format_percent,
)

LAMBDA_SOURCES = {
    "system_history": "estimated from this system's own incident history",
    "bank_wide_per_system_average": "bank-wide average per system (this system has too few incidents)",
    "user_override": "user-supplied assumption",
}
SEVERITY_SOURCES = {"system": "this system's own losses", "category": "bank-wide losses of one category",
                    "bank_wide": "all bank-wide losses"}


def render_scenario_lab() -> None:
    banner()
    st.title("Scenario Lab")
    simulation_notice()
    client = get_api_client()
    system_id = system_selector(client, "lab")
    if system_id is None:
        return
    scenarios = call_api(client.scenarios)
    # The estimated parameters do not depend on the number of simulations or the seed, so a small run is enough.
    baseline = call_api(client.simulate, system_id, 1_000, 42)
    if scenarios is None or baseline is None:
        return

    _estimated_baseline(baseline)
    settings = _inputs(scenarios["scenarios"])

    if st.button("Run baseline and stress simulation", type="primary"):
        with st.spinner("Running Monte Carlo simulations..."):
            result = _run(client, system_id, settings)
        if result is not None:
            st.session_state["lab_result"] = result
    result = st.session_state.get("lab_result")
    if result and result["system_id"] == system_id:
        _results(result)
    else:
        st.caption("Choose settings and run the simulation to see results.")


def _estimated_baseline(baseline: dict[str, Any]) -> None:
    assumptions, basis = baseline["model_assumptions"], baseline["observed_basis"]
    st.subheader("Estimated baseline model")
    columns = st.columns(3)
    columns[0].metric("λ: expected incidents per year", format_decimal(assumptions["lambda_used"]))
    columns[1].metric("μ: log-severity location", format_decimal(assumptions["severity_mu"], 3))
    columns[2].metric("σ: log-severity spread", format_decimal(assumptions["severity_sigma"], 3))
    st.caption(
        f"λ is {LAMBDA_SOURCES.get(assumptions['lambda_source'], assumptions['lambda_source'])}: "
        f"{basis['observed_incident_count']} incidents over {format_decimal(basis['observation_years'])} years. "
        f"μ and σ are fitted to {basis['severity_losses_used']} positive losses "
        f"({SEVERITY_SOURCES.get(basis['severity_data_source'], basis['severity_data_source'])})."
    )
    for note in basis["severity_fallback_notes"]:
        st.caption(f"Fallback: {note}")
    with st.expander("What do λ, μ and σ mean?"):
        st.markdown(
            "The model counts incidents per year with a **Poisson** distribution, `N ~ Poisson(λ)`, where **λ** is the "
            "expected number of incidents per year. The loss of each incident follows a **Lognormal** distribution, "
            "`X ~ Lognormal(μ, σ)`: its logarithm is bell-shaped with mean **μ** and standard deviation **σ**. So `exp(μ)` "
            "is the median loss of one incident, and a larger **σ** means a heavier tail of rare, very large losses. "
            "The annual loss is `L = X₁ + … + X_N`, simulated many times. The parameters are estimated from the "
            "synthetic history; the synthetic losses were themselves generated from Lognormal distributions, so a good "
            "fit says nothing about real losses."
        )


def _inputs(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    st.subheader("Simulation settings")
    left, right = st.columns(2)
    n = left.number_input("Number of simulations", min_value=1_000, max_value=1_000_000, value=100_000, step=10_000)
    seed = right.number_input("Random seed", min_value=0, max_value=2**32 - 1, value=42, step=1)

    ids = [s["scenario_id"] for s in scenarios]
    by_id = {s["scenario_id"]: s for s in scenarios}
    scenario_id = st.selectbox("Predefined stress scenario", ids, format_func=lambda i: by_id[i]["name"])
    scenario = by_id[scenario_id]
    st.table([{"Assumption": "λ multiplier (incident frequency)", "Value": f"{scenario['lambda_multiplier']:g}"},
              {"Assumption": "μ shift (log-severity location)", "Value": f"{scenario['severity_mu_shift']:g}"},
              {"Assumption": "σ multiplier (log-severity spread)", "Value": f"{scenario['severity_sigma_multiplier']:g}"}])
    with st.expander("Notes on this scenario's assumptions"):
        st.markdown("\n".join(f"- {note}" for note in scenario["assumption_notes"]))

    with st.expander("Advanced assumptions"):
        use_custom = st.checkbox("Use my own numbers instead of the predefined scenario")
        left, right = st.columns(2)
        lam = left.number_input("λ multiplier", min_value=0.1, max_value=100.0, value=1.5, step=0.1, disabled=not use_custom)
        sigma = right.number_input("σ multiplier", min_value=0.1, max_value=5.0, value=1.2, step=0.1, disabled=not use_custom)
        st.caption("User-supplied assumptions. They are not estimates and not calibrated, and the AI agent cannot use them.")
    return {"n": int(n), "seed": int(seed), "scenario_id": scenario_id, "use_custom": use_custom,
            "lambda_multiplier": float(lam), "sigma_multiplier": float(sigma)}


def _run(client: Any, system_id: str, s: dict[str, Any]) -> dict[str, Any] | None:
    if s["use_custom"]:
        return call_api(client.compare_custom, system_id, s["lambda_multiplier"], s["sigma_multiplier"], s["n"], s["seed"])
    return call_api(client.compare, system_id, s["scenario_id"], s["n"], s["seed"])


def _results(result: dict[str, Any]) -> None:
    out = result["simulation_results"]
    stress = result["stress_assumptions"]
    base_assumptions = result["baseline_assumptions"]
    st.subheader("Results")
    simulation_notice()
    st.markdown(f"**Stress scenario:** {stress['scenario']['name']}  \n_{stress['label']}_")

    cards = st.columns(3)
    for index, (key, label) in enumerate(METRIC_LABELS):
        cards[index % 3].metric(
            f"{label} (stress)", format_amount(out["stress_metrics"][key]),
            delta=f"{format_percent(out['percentage_differences'][key])} vs baseline {format_amount(out['baseline_metrics'][key])}",
            delta_color="inverse",
        )
    st.dataframe(comparison_rows(out), hide_index=True, width="stretch")

    st.plotly_chart(
        distribution_figure(out["baseline_histogram"], out["baseline_metrics"]["p95"],
                            out["stress_histogram"], out["stress_metrics"]["p95"]),
        width="stretch", key="loss_distribution",
    )

    parameters = stress["stress_parameters"]
    st.markdown("**Model parameters**")
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
        "same seed for baseline and stress. Closed-form mean as a check: "
        f"baseline {format_amount(out['baseline_analytic_mean_annual_loss'])}, "
        f"stress {format_amount(out['stress_analytic_mean_annual_loss'])}."
    )
    with st.expander("Model assumptions"):
        st.markdown("\n".join(f"- {s}" for s in base_assumptions["assumption_statements"]))
    with st.expander("Stress assumptions"):
        st.markdown("\n".join(f"- {note}" for note in stress["scenario"]["assumption_notes"]))
    st.caption(result["notice"])
