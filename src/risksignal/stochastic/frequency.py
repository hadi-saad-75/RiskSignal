"""Frequency model: how many incidents happen in one year?

Plain English
-------------
We cannot know how many incidents will happen next year. We model the *count* as a
random number. ``lambda`` is the average number of incidents per year; one simulated
year might have fewer or more. The Poisson model assumes incidents arrive independently
and at a steady average rate (real incidents often cluster; that is a known limitation).

Definition
----------
    N ~ Poisson(lambda),  P(N = k) = exp(-lambda) * lambda**k / k!,  E[N] = Var[N] = lambda

* ``N``      = number of incidents during one simulated year.
* ``lambda`` = expected annual number of incidents.

Estimation: if ``n`` incidents were observed over ``T`` years, the maximum likelihood
estimate of lambda is ``n / T``.
"""

from datetime import date

import numpy as np
import pandas as pd

from risksignal.stochastic.schemas import FrequencyEstimate

DAYS_PER_YEAR = 365.25
# Illustrative threshold, not a statistical guarantee: below this many incidents the
# system's own count is treated as too thin and a bank-wide average is used instead.
MIN_INCIDENTS_FOR_SYSTEM_LAMBDA = 5


def observation_years(start: date, end: date) -> float:
    """Length of the observed window in years, counting both end dates (days / 365.25)."""
    if end < start:
        raise ValueError("observation window end is before its start")
    return ((end - start).days + 1) / DAYS_PER_YEAR


def estimate_lambda_from_incidents(
    incidents: pd.DataFrame,
    system_id: str,
    observation_start: date,
    observation_end: date,
    *,
    lambda_override: float | None = None,
    min_incidents: int = MIN_INCIDENTS_FOR_SYSTEM_LAMBDA,
    n_systems: int | None = None,
) -> FrequencyEstimate:
    """Estimate the annual Poisson rate lambda for one system.

    ``incidents`` needs a ``system_id`` column (one row per incident).

    Order of preference, always reported in ``method``:

    1. ``lambda_override`` if given: a user-supplied assumption (for scenario analysis).
       The system's own historical rate is still reported for comparison.
    2. The system's own history, ``count / years``, if it has at least ``min_incidents``.
    3. Otherwise a bank-wide average per system, ``total incidents / years / n_systems``.
       ``n_systems`` is the number of systems in the bank; if omitted, the number of
       distinct systems that appear in ``incidents`` is used (which ignores systems with
       zero incidents and therefore slightly overstates the average).
    """
    if "system_id" not in incidents.columns:
        raise ValueError("incidents must have a 'system_id' column")
    if lambda_override is not None and not lambda_override > 0:
        raise ValueError("lambda_override must be a positive number")
    years = observation_years(observation_start, observation_end)
    count = int((incidents["system_id"] == system_id).sum())
    historical = count / years

    if lambda_override is not None:
        return FrequencyEstimate(
            lambda_used=lambda_override,
            method="user_override",
            lambda_historical=historical,
            observed_incidents=count,
            observation_years=years,
            note=f"User-supplied assumption. The system's own history gives {historical:.3f} per year.",
        )
    if count >= min_incidents:
        return FrequencyEstimate(
            lambda_used=historical,
            method="system_history",
            lambda_historical=historical,
            observed_incidents=count,
            observation_years=years,
            note=f"{count} incidents for {system_id} over {years:.2f} years.",
        )
    return _bank_wide_estimate(incidents, system_id, count, years, min_incidents, n_systems)


def _bank_wide_estimate(
    incidents: pd.DataFrame, system_id: str, count: int, years: float,
    min_incidents: int, n_systems: int | None,
) -> FrequencyEstimate:
    systems = n_systems if n_systems is not None else incidents["system_id"].nunique()
    if len(incidents) == 0 or systems < 1:
        raise ValueError("no incident history available to estimate lambda; supply lambda_override")
    average = len(incidents) / years / systems
    return FrequencyEstimate(
        lambda_used=average,
        method="bank_wide_per_system_average",
        lambda_historical=count / years,
        observed_incidents=count,
        observation_years=years,
        note=(
            f"{system_id} has only {count} incidents (fewer than {min_incidents}). Used the "
            f"bank-wide average of {average:.3f} incidents per system per year "
            f"({len(incidents)} incidents, {systems} systems, {years:.2f} years)."
        ),
    )


def simulate_incident_counts(
    lam: float, n_simulations: int, rng: np.random.Generator | int | None = None
) -> np.ndarray:
    """Draw ``n_simulations`` yearly incident counts N ~ Poisson(lam).

    ``rng`` may be a seed (int) or a ``numpy.random.Generator``; a given seed always
    gives the same counts.
    """
    if not lam >= 0:
        raise ValueError("lambda must be non-negative")
    if n_simulations < 1:
        raise ValueError("n_simulations must be at least 1")
    return np.random.default_rng(rng).poisson(lam, size=n_simulations)
