"""Simulation tools: wrap the stochastic engine; they calculate no statistics of their own.

Results keep three things apart: the synthetic observations used (``observed_basis``), the
model assumptions with their sources (``model_assumptions`` / ``stress_assumptions``), and
the simulated outputs (``simulation_results``).
"""

from pydantic import ValidationError

from risksignal.stochastic.scenario import (
    PREDEFINED_SCENARIOS,
    get_predefined_scenario,
    make_user_scenario,
    run_scenario_analysis,
)
from risksignal.stochastic.schemas import BaselineModel, LossMetrics, Scenario, SimulationResult
from risksignal.stochastic.simulation import run_system_simulation
from risksignal.tools.context import (
    DEFAULT_SEED,
    DEFAULT_SIMULATIONS,
    ToolContext,
    ToolFailure,
    check_simulation_settings,
    guarded,
)
from risksignal.tools.schemas import (
    LossSimulationResult,
    ModelAssumptions,
    ObservedBasis,
    ScenarioComparisonResult,
    ScenarioListResult,
    ScenarioOutputs,
    SimulationOutputs,
    StressAssumptions,
)

BASE_ASSUMPTION_STATEMENTS = [
    "Incidents per year follow a Poisson distribution: they arrive independently at a constant average rate.",
    "Each incident's loss is drawn independently from a Lognormal distribution, independent of the number of incidents.",
    "Parameters are estimated from synthetic history (or fall back as stated) and then treated as known; "
    "estimation uncertainty is not propagated.",
    "Controls, KRIs and dependencies between systems do not enter the model; each system is simulated alone.",
    "The synthetic losses were generated from Lognormal distributions, so a good fit says nothing about real losses.",
    "All parameters and results are illustrative: not calibrated to any institution and not predictive.",
]
STRESS_ASSUMPTION_STATEMENT = (
    "Stress parameters are explicit scenario assumptions applied to the baseline, not estimates from data."
)


def _basis_and_assumptions(
    result: SimulationResult,
) -> tuple[ObservedBasis, ModelAssumptions]:
    basis = ObservedBasis(
        observed_incident_count=result.observed_incident_count,
        observation_years=result.observation_years,
        severity_losses_used=result.severity_n_losses,
        severity_data_source=result.severity_data_source,
        severity_data_description=result.severity_data_description,
        severity_fallback_notes=result.severity_fallback_notes,
    )
    assumptions = ModelAssumptions(
        lambda_used=result.lambda_used,
        lambda_source=result.frequency_estimation_method,
        lambda_historical=result.lambda_historical,
        frequency_note=result.frequency_note,
        severity_mu=result.severity_mu,
        severity_sigma=result.severity_sigma,
        number_of_simulations=result.number_of_simulations,
        random_seed=result.random_seed,
        assumption_statements=BASE_ASSUMPTION_STATEMENTS,
    )
    return basis, assumptions


def _basis_and_assumptions_from_model(
    model: BaselineModel, number_of_simulations: int, random_seed: int
) -> tuple[ObservedBasis, ModelAssumptions]:
    basis = ObservedBasis(
        observed_incident_count=model.frequency.observed_incidents,
        observation_years=model.frequency.observation_years,
        severity_losses_used=model.severity.n_losses,
        severity_data_source=model.severity.data_source,
        severity_data_description=model.severity.data_description,
        severity_fallback_notes=model.severity.fallback_notes,
    )
    assumptions = ModelAssumptions(
        lambda_used=model.parameters.lambda_value,
        lambda_source=model.frequency.method,
        lambda_historical=model.frequency.lambda_historical,
        frequency_note=model.frequency.note,
        severity_mu=model.parameters.mu,
        severity_sigma=model.parameters.sigma,
        number_of_simulations=number_of_simulations,
        random_seed=random_seed,
        assumption_statements=BASE_ASSUMPTION_STATEMENTS,
    )
    return basis, assumptions


@guarded("run_loss_simulation")
def run_loss_simulation(
    ctx: ToolContext,
    system_id: str,
    number_of_simulations: int = DEFAULT_SIMULATIONS,
    random_seed: int = DEFAULT_SEED,
) -> LossSimulationResult:
    """Baseline Monte Carlo simulation of the annual aggregate loss for one system.

    Frequency and severity parameters are estimated from the system's synthetic incident
    history by the stochastic engine, with the documented fallbacks (reported in the
    result). The same seed always gives the same result. This is modelled output under
    illustrative assumptions, not a forecast.
    """
    ctx.get_system(system_id)
    n, seed = check_simulation_settings(number_of_simulations, random_seed)
    try:
        result = run_system_simulation(
            ctx.incidents_frame(), system_id,
            n_simulations=n, seed=seed,
            observation_start=ctx.observation_start, observation_end=ctx.as_of_date,
            n_systems=ctx.system_count(),
        )
    except ValueError as error:
        raise ToolFailure("model_error", f"The model could not be run: {error}") from error
    basis, assumptions = _basis_and_assumptions(result)
    return LossSimulationResult(
        tool_name="run_loss_simulation",
        system_id=system_id,
        observed_basis=basis,
        model_assumptions=assumptions,
        simulation_results=SimulationOutputs(
            metrics=LossMetrics(
                mean=result.mean_annual_loss,
                median=result.median_annual_loss,
                p95=result.p95,
                p99=result.p99,
                expected_shortfall_95=result.expected_shortfall_95,
                expected_shortfall_99=result.expected_shortfall_99,
            ),
            analytic_mean_annual_loss=result.analytic_mean_annual_loss,
            histogram=result.histogram,
        ),
    )


def _run_comparison(
    ctx: ToolContext, tool_name: str, system_id: str, scenario: Scenario, label: str, n: int, seed: int
) -> ScenarioComparisonResult:
    """Run the scenario engine and arrange its output into observed basis, assumptions and results."""
    try:
        comparison = run_scenario_analysis(
            ctx.incidents_frame(), system_id, scenario,
            n_simulations=n, seed=seed,
            observation_start=ctx.observation_start, observation_end=ctx.as_of_date,
            n_systems=ctx.system_count(),
        )
    except ValueError as error:
        raise ToolFailure("model_error", f"The model could not be run: {error}") from error
    basis, assumptions = _basis_and_assumptions_from_model(comparison.baseline_model, n, seed)
    return ScenarioComparisonResult(
        tool_name=tool_name,
        system_id=system_id,
        observed_basis=basis,
        baseline_assumptions=assumptions,
        stress_assumptions=StressAssumptions(
            scenario=comparison.scenario,
            stress_parameters=comparison.stress_parameters,
            parameter_changes=comparison.parameter_changes,
            label=f"{label} {STRESS_ASSUMPTION_STATEMENT}",
        ),
        simulation_results=ScenarioOutputs(
            baseline_metrics=comparison.baseline_metrics,
            stress_metrics=comparison.stress_metrics,
            absolute_differences=comparison.absolute_differences,
            percentage_differences=comparison.percentage_differences,
            baseline_analytic_mean_annual_loss=comparison.baseline_analytic_mean_annual_loss,
            stress_analytic_mean_annual_loss=comparison.stress_analytic_mean_annual_loss,
            baseline_histogram=comparison.baseline_histogram,
            stress_histogram=comparison.stress_histogram,
        ),
    )


@guarded("compare_baseline_and_stress")
def compare_baseline_and_stress(
    ctx: ToolContext,
    system_id: str,
    scenario_id: str,
    number_of_simulations: int = DEFAULT_SIMULATIONS,
    random_seed: int = DEFAULT_SEED,
) -> ScenarioComparisonResult:
    """Compare the baseline simulation with a predefined illustrative stress scenario.

    Only predefined scenarios can be selected (currently ``SHARED_VENDOR_OUTAGE``). Their
    numbers are illustrative assumptions, not estimates and not calibrated. Baseline and
    stress runs use the same seed.
    """
    ctx.get_system(system_id)
    if scenario_id not in PREDEFINED_SCENARIOS:
        known = sorted(PREDEFINED_SCENARIOS)
        raise ToolFailure("unknown_scenario", f"Unknown scenario '{scenario_id}'. Available: {', '.join(known)}.", known)
    n, seed = check_simulation_settings(number_of_simulations, random_seed)
    return _run_comparison(
        ctx, "compare_baseline_and_stress", system_id, get_predefined_scenario(scenario_id),
        "Stress scenario assumptions (illustrative, not calibrated).", n, seed)


@guarded("compare_baseline_and_custom_scenario")
def compare_baseline_and_custom_scenario(
    ctx: ToolContext,
    system_id: str,
    lambda_multiplier: float = 1.0,
    severity_mu_shift: float = 0.0,
    severity_sigma_multiplier: float = 1.0,
    number_of_simulations: int = DEFAULT_SIMULATIONS,
    random_seed: int = DEFAULT_SEED,
) -> ScenarioComparisonResult:
    """Compare the baseline with a stress scenario defined by explicit numbers from a person.

    Used by the UI's "Advanced assumptions". It is deliberately NOT offered to the agent, which
    may only select predefined scenarios. The numbers are user-supplied assumptions, not
    estimates, and are checked against the guard rails of the ``Scenario`` model.
    """
    ctx.get_system(system_id)
    n, seed = check_simulation_settings(number_of_simulations, random_seed)
    numbers = {"lambda_multiplier": lambda_multiplier, "severity_mu_shift": severity_mu_shift,
               "severity_sigma_multiplier": severity_sigma_multiplier}
    for name, value in numbers.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolFailure("invalid_argument", f"{name} must be a number.")
    try:
        scenario = make_user_scenario(**numbers)
    except ValidationError as error:
        first = error.errors()[0]
        raise ToolFailure("invalid_argument", f"Invalid {first['loc'][0]}: {first['msg']}.") from error
    return _run_comparison(
        ctx, "compare_baseline_and_custom_scenario", system_id, scenario,
        "Stress scenario assumptions (user-supplied, illustrative, not calibrated).", n, seed)


@guarded("list_scenarios")
def list_scenarios(ctx: ToolContext) -> ScenarioListResult:
    """The predefined illustrative scenarios with their assumptions. Offered to the chat assistant."""
    return ScenarioListResult(tool_name="list_scenarios", scenarios=[PREDEFINED_SCENARIOS[k] for k in sorted(PREDEFINED_SCENARIOS)])
