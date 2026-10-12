"""Monte Carlo engine: simulate the annual aggregate loss L = X_1 + ... + X_N.

Plain English
-------------
We "live through" many imaginary years. In each one the computer (1) randomly decides how
many incidents happen, (2) randomly decides how costly each one is, and (3) adds the
costs up. Repeating this 100,000 times gives a picture of how annual losses could turn
out *under the model's assumptions*, from which we read the average year, a bad year
(P95, P99) and the average of the worst years (Expected Shortfall).

Definition
----------
For each simulated year j = 1..M:

    N_j ~ Poisson(lambda)
    X_{j,1}, ..., X_{j,N_j}  i.i.d. ~ Lognormal(mu, sigma),  independent of N_j
    L_j = X_{j,1} + ... + X_{j,N_j}     (L_j = 0 when N_j = 0)

This is a compound Poisson model. A closed-form check exists for the mean:
E[L] = lambda * exp(mu + sigma^2 / 2); the simulated mean should be close to it.

Everything is deterministic for a given seed. Nothing in this module uses an LLM.
"""

import numpy as np
import pandas as pd
from datetime import date

from risksignal.stochastic.frequency import (
    MIN_INCIDENTS_FOR_SYSTEM_LAMBDA,
    estimate_lambda_from_incidents,
    simulate_incident_counts,
)
from risksignal.stochastic.metrics import compute_metrics, make_histogram
from risksignal.stochastic.schemas import (
    BaselineModel,
    LossHistogram,
    LossMetrics,
    ModelParameters,
    SimulationResult,
)
from risksignal.stochastic.severity import (
    MIN_LOSSES_FOR_SYSTEM_FIT,
    estimate_severity,
    lognormal_mean,
    sample_severities,
)

DEFAULT_N_SIMULATIONS = 100_000
DEFAULT_SEED = 42
# Memory guard: the engine draws about lambda * n_simulations severities at once.
MAX_EXPECTED_SEVERITY_DRAWS = 50_000_000


def aggregate_by_year(counts: np.ndarray, severities: np.ndarray) -> np.ndarray:
    """Sum severities within each simulated year.

    ``severities`` holds all individual losses back to back: first ``counts[0]`` belong to
    year 0, the next ``counts[1]`` to year 1, and so on. Years with zero incidents get 0.
    """
    if int(counts.sum()) != len(severities):
        raise ValueError("number of severities must equal the sum of the incident counts")
    year_index = np.repeat(np.arange(len(counts)), counts)
    return np.bincount(year_index, weights=severities, minlength=len(counts))


def simulate_annual_losses(
    lam: float, mu: float, sigma: float, n_simulations: int,
    rng: np.random.Generator | int | None = None,
) -> np.ndarray:
    """Simulate ``n_simulations`` annual aggregate losses (non-negative, one per year).

    ``rng`` may be a seed (int) or a ``numpy.random.Generator``. Counts are drawn first,
    then all severities in one vectorised call, so 100,000 years take well under a second.
    """
    if lam * n_simulations > MAX_EXPECTED_SEVERITY_DRAWS:
        raise ValueError(
            f"lambda * n_simulations = {lam * n_simulations:,.0f} severity draws exceeds the "
            f"limit of {MAX_EXPECTED_SEVERITY_DRAWS:,}; reduce n_simulations or lambda"
        )
    generator = np.random.default_rng(rng)
    counts = simulate_incident_counts(lam, n_simulations, generator)
    severities = sample_severities(mu, sigma, int(counts.sum()), generator)
    return aggregate_by_year(counts, severities)


def _observation_window(
    incidents: pd.DataFrame, start: date | None, end: date | None
) -> tuple[date, date]:
    """Use the given window, or fall back to the first and last incident dates in the bank."""
    if start is not None and end is not None:
        return start, end
    dates = pd.to_datetime(incidents["date"]).dt.date
    return (start or dates.min()), (end or dates.max())


def build_baseline_model(
    incidents: pd.DataFrame,
    system_id: str,
    *,
    observation_start: date | None = None,
    observation_end: date | None = None,
    lambda_override: float | None = None,
    category: str | None = None,
    n_systems: int | None = None,
    min_incidents: int = MIN_INCIDENTS_FOR_SYSTEM_LAMBDA,
    min_losses: int = MIN_LOSSES_FOR_SYSTEM_FIT,
) -> BaselineModel:
    """Estimate baseline parameters (lambda, mu, sigma) from synthetic historical incidents.

    ``incidents`` is a table with columns ``date``, ``system_id``, ``category`` and
    ``financial_loss`` (one row per incident).

    * Pass ``observation_start`` and ``observation_end`` (the true span of the data) for
      a correct lambda. If omitted, the first and last incident dates in ``incidents`` are
      used, which slightly understates the window.
    * ``lambda_override`` replaces the estimated lambda (a user-supplied assumption).
    * ``category`` models only incidents of that category: both lambda and severity
      then use only that category's incidents.

    The returned object also records how each parameter was obtained.
    """
    start, end = _observation_window(incidents, observation_start, observation_end)
    systems = n_systems if n_systems is not None else int(incidents["system_id"].nunique())
    scope = incidents if category is None else incidents[incidents["category"] == category]

    frequency = estimate_lambda_from_incidents(
        scope, system_id, start, end,
        lambda_override=lambda_override, min_incidents=min_incidents, n_systems=systems,
    )
    severity = estimate_severity(incidents, system_id, category=category, min_losses=min_losses)
    return BaselineModel(
        system_id=system_id,
        incident_category=category,
        parameters=ModelParameters(lambda_value=frequency.lambda_used, mu=severity.mu, sigma=severity.sigma),
        frequency=frequency,
        severity=severity,
    )


def analytic_mean_annual_loss(parameters: ModelParameters) -> float:
    """Closed-form E[L] = lambda * exp(mu + sigma^2 / 2) (computed, not simulated)."""
    return parameters.lambda_value * lognormal_mean(parameters.mu, parameters.sigma)


def simulate_parameters(
    parameters: ModelParameters,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    histogram_bins: int | None = 50,
) -> tuple[LossMetrics, LossHistogram | None]:
    """Simulate annual losses for given parameters and summarise them. Deterministic per seed."""
    losses = simulate_annual_losses(
        parameters.lambda_value, parameters.mu, parameters.sigma, n_simulations, seed
    )
    histogram = None if histogram_bins is None else make_histogram(losses, histogram_bins)
    return compute_metrics(losses), histogram


def run_system_simulation(
    incidents: pd.DataFrame,
    system_id: str,
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
) -> SimulationResult:
    """Estimate parameters from history, simulate, and summarise, for one system.

    See ``build_baseline_model`` for the data arguments. ``histogram_bins=None`` omits
    the histogram.
    """
    model = build_baseline_model(
        incidents, system_id,
        observation_start=observation_start, observation_end=observation_end,
        lambda_override=lambda_override, category=category, n_systems=n_systems,
        min_incidents=min_incidents, min_losses=min_losses,
    )
    metrics, histogram = simulate_parameters(model.parameters, n_simulations, seed, histogram_bins)
    frequency, severity = model.frequency, model.severity

    return SimulationResult(
        system_id=system_id,
        incident_category=category,
        lambda_used=frequency.lambda_used,
        frequency_estimation_method=frequency.method,
        lambda_historical=frequency.lambda_historical,
        observed_incident_count=frequency.observed_incidents,
        observation_years=frequency.observation_years,
        frequency_note=frequency.note,
        severity_mu=severity.mu,
        severity_sigma=severity.sigma,
        severity_data_source=severity.data_source,
        severity_data_description=severity.data_description,
        severity_n_losses=severity.n_losses,
        severity_fallback_notes=severity.fallback_notes,
        number_of_simulations=n_simulations,
        random_seed=seed,
        mean_annual_loss=metrics.mean,
        median_annual_loss=metrics.median,
        p95=metrics.p95,
        p99=metrics.p99,
        expected_shortfall_95=metrics.expected_shortfall_95,
        expected_shortfall_99=metrics.expected_shortfall_99,
        analytic_mean_annual_loss=analytic_mean_annual_loss(model.parameters),
        histogram=histogram,
    )
