"""Tests for risk metrics (percentiles, Expected Shortfall, histogram)."""

import numpy as np
import pytest

from risksignal.stochastic.metrics import (
    compute_metrics,
    expected_shortfall,
    make_histogram,
    value_at_risk,
)

ONE_TO_HUNDRED = np.arange(1.0, 101.0)


def test_known_values_on_one_to_one_hundred() -> None:
    metrics = compute_metrics(ONE_TO_HUNDRED)
    assert metrics.mean == pytest.approx(50.5)
    assert metrics.median == pytest.approx(50.5)
    assert metrics.p95 == 95.0  # 95 of the 100 years are <= 95
    assert metrics.p99 == 99.0
    assert metrics.expected_shortfall_95 == pytest.approx(98.0)  # mean of 96..100
    assert metrics.expected_shortfall_99 == pytest.approx(100.0)  # the single worst year


def test_expected_shortfall_handles_fractional_tail_mass() -> None:
    # 30 years, alpha = 0.95: tail mass = 1.5 years = all of 30 plus half of 29
    values = np.arange(1.0, 31.0)
    assert expected_shortfall(values, 0.95) == pytest.approx((30 + 0.5 * 29) / 1.5)
    # 10 years: tail mass 0.5 year, entirely inside the worst year
    assert expected_shortfall(np.arange(1.0, 11.0), 0.95) == pytest.approx(10.0)


def test_input_order_does_not_matter() -> None:
    shuffled = np.random.default_rng(0).permutation(ONE_TO_HUNDRED)
    assert compute_metrics(shuffled) == compute_metrics(ONE_TO_HUNDRED)


def test_ties_and_many_zero_years() -> None:
    # 97% of years have zero loss. P95 is 0, and ES must still be >= VaR and meaningful.
    losses = np.concatenate([np.zeros(970), np.full(30, 1_000.0)])
    metrics = compute_metrics(losses)
    assert metrics.p95 == 0.0
    assert metrics.expected_shortfall_95 == pytest.approx(30 * 1_000.0 / 50)  # 30 of the worst 50 years
    assert metrics.expected_shortfall_99 == pytest.approx(1_000.0)
    assert metrics.expected_shortfall_95 >= metrics.p95
    assert compute_metrics(np.zeros(100)).expected_shortfall_99 == 0.0


def test_ordering_and_es_dominate_var_on_skewed_losses() -> None:
    losses = np.random.default_rng(4).lognormal(10.0, 1.5, 100_000)
    metrics = compute_metrics(losses)
    assert metrics.median <= metrics.p95 <= metrics.p99
    assert metrics.expected_shortfall_95 >= metrics.p95
    assert metrics.expected_shortfall_99 >= metrics.p99
    assert metrics.expected_shortfall_99 >= metrics.expected_shortfall_95
    assert metrics.mean > metrics.median  # right skew


def test_es_dominates_var_for_awkward_sample_sizes() -> None:
    rng = np.random.default_rng(8)
    for size in (1, 2, 7, 33, 101, 999):
        losses = rng.lognormal(0.0, 1.0, size)
        for alpha in (0.5, 0.95, 0.99):
            assert expected_shortfall(losses, alpha) >= value_at_risk(losses, alpha) - 1e-12


@pytest.mark.parametrize("bad", [[], [1.0, -1.0], [1.0, float("nan")], [[1.0, 2.0]]])
def test_invalid_losses_are_rejected(bad: list) -> None:
    with pytest.raises(ValueError):
        compute_metrics(np.array(bad))


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
def test_invalid_alpha_is_rejected(alpha: float) -> None:
    with pytest.raises(ValueError):
        value_at_risk(ONE_TO_HUNDRED, alpha)
    with pytest.raises(ValueError):
        expected_shortfall(ONE_TO_HUNDRED, alpha)


def test_histogram_accounts_for_every_year() -> None:
    losses = np.random.default_rng(2).lognormal(10.0, 1.5, 50_000)
    hist = make_histogram(losses, bins=40)
    assert len(hist.counts) == 40
    assert len(hist.bin_edges) == 41
    assert hist.bin_edges[0] == 0.0
    assert sum(hist.counts) + hist.overflow_count == len(losses)
    assert hist.overflow_count == pytest.approx(0.01 * len(losses), rel=0.05)  # above the 99th percentile


def test_histogram_of_all_zero_losses_is_valid() -> None:
    hist = make_histogram(np.zeros(100), bins=5)
    assert sum(hist.counts) == 100
    assert hist.overflow_count == 0
