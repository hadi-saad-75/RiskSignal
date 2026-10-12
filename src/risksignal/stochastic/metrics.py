"""Risk metrics computed from simulated annual losses.

Plain English
-------------
After simulating many hypothetical years we have a long list of annual losses.

* **Mean**   : the average year.
* **Median** : the typical year; half of years are better, half worse.
* **P95 / P99** (95th / 99th percentile, also called Value-at-Risk): the loss level
  that is exceeded in only about 1 year in 20 / 1 year in 100.
* **Expected Shortfall 95 (ES95)**: if P95 is the threshold exceeded in the worst 5% of
  simulated years, ES95 is the *average loss within those worst 5%*. It answers "how bad
  is a bad year, once we are past the P95 line?". ES99 is the same for the worst 1%.

Definitions
-----------
For the annual loss L and a level alpha (0.95 or 0.99):

    VaR_alpha = inf { x : P(L <= x) >= alpha }          (empirical: ``inverted_cdf``)
    ES_alpha  = E[ L | L >= VaR_alpha ]                 (average of the worst 1-alpha of mass)

Estimator used for ES (Acerbi-Tasche form), with M simulated years sorted ascending:
average of the top ``M * (1 - alpha)`` observations, where a fractional number of
observations is handled by giving the boundary observation a fractional weight. This
gives ES >= VaR exactly, even when many years have identical losses (for example zero).

Tail estimates are noisy: the 99% level uses only 1% of the simulated years.
"""

import numpy as np

from risksignal.stochastic.schemas import LossHistogram, LossMetrics


def _validated(losses: np.ndarray) -> np.ndarray:
    values = np.asarray(losses, dtype=float)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("losses must be a non-empty 1-D array")
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("losses must be finite and non-negative")
    return values


def value_at_risk(losses: np.ndarray, alpha: float) -> float:
    """Empirical VaR_alpha: the smallest simulated loss x with at least a share alpha of years <= x."""
    _check_alpha(alpha)
    return float(np.quantile(_validated(losses), alpha, method="inverted_cdf"))


def expected_shortfall(losses: np.ndarray, alpha: float) -> float:
    """Average annual loss within the worst ``1 - alpha`` share of simulated years."""
    _check_alpha(alpha)
    ordered = np.sort(_validated(losses))
    tail_mass = len(ordered) * (1.0 - alpha)  # number of years in the tail, possibly fractional
    whole = int(tail_mass)
    total = float(ordered[len(ordered) - whole:].sum()) if whole > 0 else 0.0
    fraction = tail_mass - whole
    if fraction > 0 and whole < len(ordered):
        total += fraction * float(ordered[len(ordered) - whole - 1])
    return total / tail_mass


def compute_metrics(losses: np.ndarray) -> LossMetrics:
    """Mean, median, P95, P99, ES95 and ES99 of simulated annual losses."""
    values = _validated(losses)
    return LossMetrics(
        mean=float(values.mean()),
        median=float(np.median(values)),
        p95=value_at_risk(values, 0.95),
        p99=value_at_risk(values, 0.99),
        expected_shortfall_95=expected_shortfall(values, 0.95),
        expected_shortfall_99=expected_shortfall(values, 0.99),
    )


def make_histogram(losses: np.ndarray, bins: int = 50, upper_quantile: float = 0.99) -> LossHistogram:
    """Compact histogram over [0, upper_quantile of losses].

    The range stops at a high quantile because the loss distribution is right-skewed:
    a few extreme years would otherwise squeeze almost all of the data into one bar.
    Years above the range are counted in ``overflow_count``, so
    ``sum(counts) + overflow_count`` equals the number of simulated years.
    """
    values = _validated(losses)
    if bins < 1:
        raise ValueError("bins must be at least 1")
    upper = float(np.quantile(values, upper_quantile, method="inverted_cdf"))
    if upper <= 0:
        upper = 1.0
    edges = np.linspace(0.0, upper, bins + 1)
    in_range = values[values <= upper]
    counts, _ = np.histogram(in_range, bins=edges)
    return LossHistogram(
        bin_edges=[float(e) for e in edges],
        counts=[int(c) for c in counts],
        overflow_count=int(len(values) - len(in_range)),
        upper_limit_description=f"{upper_quantile:.0%} percentile of simulated annual losses",
    )


def _check_alpha(alpha: float) -> None:
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be strictly between 0 and 1")
