"""Transparent temporal diagnostics reusing the existing frequency-severity model."""

import numpy as np
import pandas as pd
from scipy.stats import poisson

from risksignal.stochastic.frequency import observation_years
from risksignal.stochastic.schemas import TemporalDiagnostics
from risksignal.stochastic.simulation import build_baseline_model
from datetime import date


def evaluate_temporal_model(
    frame: pd.DataFrame, system_id: str, observation_start: date, as_of_date: date, n_systems: int,
) -> TemporalDiagnostics:
    """Fit on earlier history only and inspect the final twelve months, without refitting."""
    cutoff = (pd.Timestamp(as_of_date) - pd.DateOffset(months=12)).date()
    dates = pd.to_datetime(frame["date"]).dt.date
    losses = frame["financial_loss"].to_numpy(dtype=float)
    if not np.all(np.isfinite(losses)) or np.any(losses < 0):
        raise ValueError("Incident losses must be finite and non-negative.")
    training = frame[(dates >= observation_start) & (dates <= cutoff)].copy()
    holdout = frame[(dates > cutoff) & (dates <= as_of_date) & (frame["system_id"] == system_id)]
    own_training = training[training["system_id"] == system_id]
    positive = holdout.loc[holdout["financial_loss"] > 0, "financial_loss"].to_numpy(dtype=float)
    basis = dict(
        system_id=system_id, as_of_date=as_of_date,
        training_start=observation_start, training_end_inclusive=cutoff,
        holdout_end_inclusive=as_of_date, training_incidents=len(own_training),
        holdout_incidents=len(holdout), holdout_positive_losses=len(positive),
    )
    limitations = [
        "A single synthetic temporal holdout is not evidence of real-world predictive validity or independent approval.",
        "Parameters and any bank-wide pooling use training rows only. The holdout is not used for fitting.",
        "Count reference interval is conditional on a fitted Poisson rate and excludes parameter uncertainty.",
        "Variance/mean is descriptive, not a significance test. Monthly seasonality and clustering are not modelled.",
        "Positive-loss Lognormal fitting excludes zero losses, while frequency counts all incidents. No zero-loss mixture is fitted.",
        "Small samples, pooling, constructed Lognormal data and one holdout limit interpretation of tail exceedances.",
        "Diagnostics do not calculate Basel SMA capital or certify DORA, EU AI Act or PRA compliance.",
    ]
    if cutoff <= observation_start:
        return TemporalDiagnostics(
            **basis, status="not_estimable",
            limitations=["No training window remains before the twelve-month holdout.", *limitations],
        )
    try:
        model = build_baseline_model(
            training, system_id, observation_start=observation_start,
            observation_end=cutoff, n_systems=n_systems,
        )
    except ValueError as error:
        return TemporalDiagnostics(
            **basis, status="not_estimable", limitations=[f"Model cannot be fitted: {error}", *limitations],
        )
    expected = model.parameters.lambda_value * (
        observation_years(cutoff, as_of_date) - observation_years(cutoff, cutoff)
    )
    interval = poisson.interval(0.95, expected)
    first_month = pd.Timestamp(observation_start).to_period("M")
    last_month = pd.Timestamp(cutoff).to_period("M")
    # Partial boundary months have unequal exposure, so omit them from dispersion.
    full_months = [
        p for p in pd.period_range(first_month, last_month, freq="M")
        if p.start_time.date() >= observation_start and p.end_time.date() <= cutoff
    ]
    counts = pd.to_datetime(own_training["date"]).dt.to_period("M").value_counts().reindex(full_months, fill_value=0)
    mean = float(counts.mean()) if len(counts) else 0.0
    dispersion = float(counts.var(ddof=1) / mean) if len(counts) > 1 and mean > 0 else None
    p95 = float(np.exp(model.parameters.mu + model.parameters.sigma * 1.6448536269514722))
    return TemporalDiagnostics(
        **basis, status="evaluated",
        frequency_method=model.frequency.method, severity_source=model.severity.data_source,
        severity_training_losses=model.severity.n_losses,
        annual_frequency=model.parameters.lambda_value,
        severity_mu=model.parameters.mu, severity_sigma=model.parameters.sigma,
        expected_holdout_count=expected, count_reference_interval_95=(int(interval[0]), int(interval[1])),
        monthly_count_variance_to_mean=dispersion, severity_p95=p95,
        holdout_losses_above_p95=int(np.sum(positive > p95)), limitations=limitations,
    )
