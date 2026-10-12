"""Severity model: how large is the loss of one incident?

Plain English
-------------
Most incidents cost a little and a few cost a great deal. A loss can never be negative,
and the "few huge ones" give the distribution a long right tail. The Lognormal
distribution has exactly these two features, which makes it a common illustrative
choice. It is NOT claimed to be the correct distribution for real bank losses; here it
is simply a transparent example, and the synthetic data were themselves generated from
Lognormal distributions, so a good fit proves nothing about the real world.

Definition
----------
    X ~ Lognormal(mu, sigma)   means   ln X ~ Normal(mu, sigma^2)

* ``mu``    = mean of the *logarithm* of the loss (log space). exp(mu) is the median loss.
* ``sigma`` = standard deviation of the logarithm of the loss. Bigger sigma means a
  heavier right tail.  ``mu`` and ``sigma`` are NOT the mean and standard deviation of
  the loss itself. The loss has mean E[X] = exp(mu + sigma^2 / 2).
* Because ln X must exist, losses must be strictly positive.

Fitting: with positive losses x_1..x_n, the maximum likelihood estimates are
    mu_hat = mean(ln x_i),   sigma_hat^2 = mean((ln x_i - mu_hat)^2)   (divide by n).

Which data are used (never switched silently)
---------------------------------------------
1. ``system``    : positive losses of the selected system (and category, if requested).
2. ``category``  : bank-wide losses of the requested incident category (only if a
                   category was requested).
3. ``bank_wide`` : all bank-wide positive losses.
The most specific level with at least ``min_losses`` positive losses is used. The result
records which level was used and why more specific ones were skipped.
"""

import math

import numpy as np
import pandas as pd

from risksignal.stochastic.schemas import SeverityDataSource, SeverityEstimate

# Illustrative threshold, not a statistical guarantee. Even 15 losses give a very
# uncertain sigma (roughly +/- 20%), and high percentiles are sensitive to sigma.
MIN_LOSSES_FOR_SYSTEM_FIT = 15


def fit_lognormal(losses: np.ndarray | list[float]) -> tuple[float, float]:
    """Fit Lognormal parameters (mu, sigma) in log space by maximum likelihood.

    Raises ``ValueError`` unless there are at least 2 losses and all are positive
    and finite.
    """
    values = np.asarray(losses, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("need at least 2 losses to fit a Lognormal")
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("Lognormal fitting needs strictly positive, finite losses")
    logs = np.log(values)
    return float(logs.mean()), float(logs.std(ddof=0))


def lognormal_mean(mu: float, sigma: float) -> float:
    """E[X] = exp(mu + sigma^2 / 2) for X ~ Lognormal(mu, sigma)."""
    return math.exp(mu + sigma**2 / 2.0)


def sample_severities(
    mu: float, sigma: float, size: int, rng: np.random.Generator | int | None = None
) -> np.ndarray:
    """Draw ``size`` i.i.d. losses X ~ Lognormal(mu, sigma). All values are positive."""
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    if size < 0:
        raise ValueError("size must be non-negative")
    return np.random.default_rng(rng).lognormal(mean=mu, sigma=sigma, size=size)


def _positive_losses(rows: pd.DataFrame) -> np.ndarray:
    losses = rows["financial_loss"].to_numpy(dtype=float)
    return losses[np.isfinite(losses) & (losses > 0)]


def _check_columns(incidents: pd.DataFrame, category: str | None) -> None:
    required = {"system_id", "financial_loss"} | ({"category"} if category is not None else set())
    missing = required - set(incidents.columns)
    if missing:
        raise ValueError(f"incidents is missing columns: {sorted(missing)}")


def estimate_severity(
    incidents: pd.DataFrame,
    system_id: str,
    *,
    category: str | None = None,
    min_losses: int = MIN_LOSSES_FOR_SYSTEM_FIT,
) -> SeverityEstimate:
    """Fit the illustrative Lognormal severity model and report which data were used.

    See the module docstring for the fallback hierarchy. Raises ``ValueError`` if even
    the bank-wide data have fewer than ``min_losses`` positive losses.
    """
    _check_columns(incidents, category)
    in_category = incidents if category is None else incidents[incidents["category"] == category]
    candidates: list[tuple[SeverityDataSource, str, np.ndarray]] = [
        ("system", _system_label(system_id, category), _positive_losses(in_category[in_category["system_id"] == system_id])),
    ]
    if category is not None:
        candidates.append(("category", f"bank-wide losses of category '{category}'", _positive_losses(in_category)))
    candidates.append(("bank_wide", "all bank-wide losses", _positive_losses(incidents)))

    notes: list[str] = []
    for source, label, losses in candidates:
        if len(losses) >= min_losses:
            mu, sigma = fit_lognormal(losses)
            return SeverityEstimate(
                mu=mu, sigma=sigma, n_losses=len(losses), data_source=source,
                data_description=f"{len(losses)} positive losses: {label}.", fallback_notes=notes,
            )
        notes.append(f"{label}: {len(losses)} positive losses, fewer than the {min_losses} required.")
    raise ValueError("not enough positive losses to fit a severity model. " + " ".join(notes))


def _system_label(system_id: str, category: str | None) -> str:
    if category is None:
        return f"losses of {system_id}"
    return f"losses of {system_id} in category '{category}'"
