"""Transparent stress scenarios on top of the baseline frequency-severity model.

Plain English
-------------
A *scenario* is a "what if" written as explicit numbers. "What if incidents happen 1.8 times
as often, and each one is somewhat more costly?" The scenario engine takes the baseline
model (estimated from synthetic history), applies those numbers, simulates both versions
from common random numbers, and shows the two side by side with the differences.

The numbers are assumptions made by a person. They are NOT derived from data, NOT
calibrated, and NOT produced by an LLM. Nothing here works out causes: a scenario does not
look at the dependency graph and does not know which systems share a vendor. The user
chooses the system and the numbers.

Definition
----------
Given baseline parameters (lambda, mu, sigma) and a scenario (m_lambda, delta_mu, m_sigma):

    lambda_stress = m_lambda * lambda
    mu_stress     = mu + delta_mu
    sigma_stress  = m_sigma * sigma

The stress run uses the same model (compound Poisson-Lognormal) and the same number of
simulations as the baseline, and is simulated with COMMON RANDOM NUMBERS: simulated year j
of the stress run is built from the same random events as year j of the baseline (see
``simulate_paired_annual_losses``). Using the same seed alone would not do this, because
different lambdas consume the random stream differently. Coupling removes most of the sampling
noise from the comparison; a scenario that changes nothing gives results identical to the
baseline, and a scenario that can only add loss (more incidents, higher mu, same sigma) gives a
stressed loss that is at least the baseline loss in every simulated year.
"""

import math
from datetime import date

import pandas as pd

from risksignal.stochastic.frequency import MIN_INCIDENTS_FOR_SYSTEM_LAMBDA
from risksignal.stochastic.schemas import (
    BaselineModel,
    LossMetrics,
    MetricDifferences,
    MetricPercentChanges,
    ModelParameters,
    ParameterChanges,
    Scenario,
    ScenarioComparison,
)
from risksignal.stochastic.severity import MIN_LOSSES_FOR_SYSTEM_FIT
from risksignal.stochastic.simulation import (
    DEFAULT_N_SIMULATIONS,
    DEFAULT_SEED,
    analytic_mean_annual_loss,
    build_baseline_model,
    simulate_paired_annual_losses,
    summarise_losses,
)

METRIC_NAMES = ("mean", "median", "p95", "p99", "expected_shortfall_95", "expected_shortfall_99")

# --------------------------------------------------------------------------- predefined scenario

_VENDOR_LAMBDA_MULTIPLIER = 1.8
_VENDOR_MU_SHIFT = 0.20
_VENDOR_SIGMA_MULTIPLIER = 1.10

SHARED_VENDOR_OUTAGE = Scenario(
    scenario_id="SHARED_VENDOR_OUTAGE",
    name="Shared vendor outage (illustrative stress)",
    description=(
        "Illustrative stress for a year in which an external vendor used by the system suffers "
        "outages: incidents are assumed to be more frequent and each one more costly, with a "
        "heavier right tail. Intended for the demonstration on PAYMENT_ENGINE_01, which shares "
        "a vendor with PAYMENT_ENGINE_02."
    ),
    lambda_multiplier=_VENDOR_LAMBDA_MULTIPLIER,
    severity_mu_shift=_VENDOR_MU_SHIFT,
    severity_sigma_multiplier=_VENDOR_SIGMA_MULTIPLIER,
    assumption_notes=[
        "ILLUSTRATIVE ONLY: these numbers were chosen to demonstrate the mechanics. They are "
        "not empirically calibrated, not validated by experts and have no institutional validity.",
        f"lambda_multiplier = {_VENDOR_LAMBDA_MULTIPLIER}: assumes {_VENDOR_LAMBDA_MULTIPLIER} times as many "
        "incidents per year as the baseline estimate.",
        f"severity_mu_shift = {_VENDOR_MU_SHIFT:+}: moves the log-median loss up by {_VENDOR_MU_SHIFT}, "
        f"multiplying the median incident loss by exp({_VENDOR_MU_SHIFT}) = {math.exp(_VENDOR_MU_SHIFT):.3f}.",
        f"severity_sigma_multiplier = {_VENDOR_SIGMA_MULTIPLIER}: widens the spread of log losses by "
        f"{(_VENDOR_SIGMA_MULTIPLIER - 1):.0%}, giving a heavier right tail.",
        "No causal link between a vendor event and these numbers has been derived or tested. The "
        "scenario does not use the dependency graph; the user chooses which system it is applied to.",
        "The system is simulated alone. A real vendor outage would hit all systems sharing the vendor "
        "at the same time; that dependence is not modelled.",
    ],
    provenance="predefined_illustrative",
)

PREDEFINED_SCENARIOS: dict[str, Scenario] = {SHARED_VENDOR_OUTAGE.scenario_id: SHARED_VENDOR_OUTAGE}


def get_predefined_scenario(scenario_id: str) -> Scenario:
    """Look up a predefined illustrative scenario by ID."""
    try:
        return PREDEFINED_SCENARIOS[scenario_id]
    except KeyError:
        known = ", ".join(sorted(PREDEFINED_SCENARIOS))
        raise ValueError(f"unknown scenario_id '{scenario_id}'. Known scenarios: {known}") from None


# --------------------------------------------------------------------------- user scenarios


def make_user_scenario(
    lambda_multiplier: float = 1.0,
    severity_mu_shift: float = 0.0,
    severity_sigma_multiplier: float = 1.0,
    *,
    name: str = "User-defined scenario",
    scenario_id: str = "USER_DEFINED",
) -> Scenario:
    """Build a scenario from explicit numbers (no free-text generation).

    Values outside the guard rails of ``Scenario`` raise a validation error.
    """
    return Scenario(
        scenario_id=scenario_id,
        name=name,
        description=(
            f"User-supplied stress: lambda x {lambda_multiplier:g}, log-severity mean shifted by "
            f"{severity_mu_shift:+g}, log-severity sigma x {severity_sigma_multiplier:g}."
        ),
        lambda_multiplier=lambda_multiplier,
        severity_mu_shift=severity_mu_shift,
        severity_sigma_multiplier=severity_sigma_multiplier,
        assumption_notes=["User-supplied numerical assumptions. Not calibrated or validated."],
        provenance="user_supplied",
    )


# --------------------------------------------------------------------------- applying and comparing


def apply_scenario(baseline: ModelParameters, scenario: Scenario) -> ModelParameters:
    """Return stress parameters; the baseline object is not modified."""
    return ModelParameters(
        lambda_value=baseline.lambda_value * scenario.lambda_multiplier,
        mu=baseline.mu + scenario.severity_mu_shift,
        sigma=baseline.sigma * scenario.severity_sigma_multiplier,
    )


def _percent_change(baseline: float, stress: float) -> float | None:
    """100 * (stress - baseline) / baseline, or None when the baseline is zero."""
    if baseline == 0:
        return None
    return 100.0 * (stress - baseline) / baseline


def compare_metrics(baseline: LossMetrics, stress: LossMetrics) -> tuple[MetricDifferences, MetricPercentChanges]:
    """Absolute and percentage differences (stress relative to baseline) for every metric."""
    absolute = {name: getattr(stress, name) - getattr(baseline, name) for name in METRIC_NAMES}
    percent = {name: _percent_change(getattr(baseline, name), getattr(stress, name)) for name in METRIC_NAMES}
    return MetricDifferences(**absolute), MetricPercentChanges(**percent)


def _parameter_changes(baseline: ModelParameters, stress: ModelParameters) -> ParameterChanges:
    return ParameterChanges(
        lambda_absolute=stress.lambda_value - baseline.lambda_value,
        lambda_percent=100.0 * (stress.lambda_value - baseline.lambda_value) / baseline.lambda_value,
        mu_absolute=stress.mu - baseline.mu,
        sigma_absolute=stress.sigma - baseline.sigma,
        sigma_percent=_percent_change(baseline.sigma, stress.sigma),
    )


def compare_scenario(
    baseline_model: BaselineModel,
    scenario: Scenario,
    *,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    histogram_bins: int | None = 50,
) -> ScenarioComparison:
    """Simulate the baseline and the stressed model from common random numbers and compare them."""
    baseline = baseline_model.parameters
    stress = apply_scenario(baseline, scenario)
    baseline_losses, stress_losses = simulate_paired_annual_losses(baseline, stress, n_simulations, seed)
    baseline_metrics, baseline_histogram = summarise_losses(baseline_losses, histogram_bins)
    stress_metrics, stress_histogram = summarise_losses(stress_losses, histogram_bins)
    absolute, percent = compare_metrics(baseline_metrics, stress_metrics)

    return ScenarioComparison(
        system_id=baseline_model.system_id,
        scenario=scenario,
        baseline_model=baseline_model,
        baseline_parameters=baseline,
        stress_parameters=stress,
        parameter_changes=_parameter_changes(baseline, stress),
        baseline_metrics=baseline_metrics,
        stress_metrics=stress_metrics,
        absolute_differences=absolute,
        percentage_differences=percent,
        baseline_analytic_mean_annual_loss=analytic_mean_annual_loss(baseline),
        stress_analytic_mean_annual_loss=analytic_mean_annual_loss(stress),
        number_of_simulations=n_simulations,
        random_seed=seed,
        baseline_histogram=baseline_histogram,
        stress_histogram=stress_histogram,
    )


def run_scenario_analysis(
    incidents: pd.DataFrame,
    system_id: str,
    scenario: Scenario,
    *,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    observation_start: date | None = None,
    observation_end: date | None = None,
    lambda_override: float | None = None,
    category: str | None = None,
    n_systems: int | None = None,
    min_incidents: int = MIN_INCIDENTS_FOR_SYSTEM_LAMBDA,
    min_losses: int = MIN_LOSSES_FOR_SYSTEM_FIT,
    histogram_bins: int | None = 50,
) -> ScenarioComparison:
    """Build the baseline model from synthetic incidents, apply ``scenario`` and compare.

    The baseline arguments are the same as in ``build_baseline_model``. If
    ``lambda_override`` is given, the scenario multiplies that user-supplied lambda.
    """
    model = build_baseline_model(
        incidents, system_id,
        observation_start=observation_start, observation_end=observation_end,
        lambda_override=lambda_override, category=category, n_systems=n_systems,
        min_incidents=min_incidents, min_losses=min_losses,
    )
    return compare_scenario(
        model, scenario, n_simulations=n_simulations, seed=seed, histogram_bins=histogram_bins
    )
