"""Tests for the Lognormal severity model and its data-selection hierarchy."""

import math

import numpy as np
import pandas as pd
import pytest

from risksignal.stochastic.severity import (
    estimate_severity,
    fit_lognormal,
    lognormal_mean,
    sample_severities,
)


def test_fit_recovers_known_log_space_parameters_exactly() -> None:
    # ln(x) = 1, 2, 3  ->  mean 2, population standard deviation sqrt(2/3)
    mu, sigma = fit_lognormal([math.exp(1), math.exp(2), math.exp(3)])
    assert mu == pytest.approx(2.0)
    assert sigma == pytest.approx(math.sqrt(2.0 / 3.0))


def test_fit_recovers_parameters_from_a_large_sample() -> None:
    sample = sample_severities(9.0, 1.2, 200_000, 7)
    mu, sigma = fit_lognormal(sample)
    assert mu == pytest.approx(9.0, abs=0.02)
    assert sigma == pytest.approx(1.2, abs=0.02)


@pytest.mark.parametrize("bad", [[1.0], [], [1.0, 0.0], [1.0, -2.0], [1.0, float("nan")], [1.0, float("inf")]])
def test_fit_rejects_unusable_losses(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        fit_lognormal(bad)


def test_sampled_severities_are_strictly_positive_and_right_skewed() -> None:
    sample = sample_severities(10.0, 1.5, 100_000, 3)
    assert sample.min() > 0
    assert sample.mean() > np.median(sample)  # long right tail pulls the mean above the median
    assert np.median(sample) == pytest.approx(math.exp(10.0), rel=0.03)  # exp(mu) is the median


def test_sampled_mean_matches_closed_form() -> None:
    mu, sigma = 10.0, 0.5
    sample = sample_severities(mu, sigma, 300_000, 11)
    assert sample.mean() == pytest.approx(lognormal_mean(mu, sigma), rel=0.01)


def test_severity_sampling_is_reproducible() -> None:
    assert np.array_equal(sample_severities(1.0, 1.0, 100, 9), sample_severities(1.0, 1.0, 100, 9))
    assert sample_severities(1.0, 1.0, 0, 9).size == 0


def test_invalid_sampling_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        sample_severities(1.0, -0.1, 10, 1)
    with pytest.raises(ValueError):
        sample_severities(1.0, 1.0, -1, 1)


# ----------------------------------------------------------------- data selection hierarchy


def incident_table() -> pd.DataFrame:
    """Deterministic losses: S1 has 20 (A), S2 has 3 (A) and 3 (B), S3 has 2; bank has 28."""
    rows = []
    for system, category, n in [("S1", "A", 20), ("S2", "A", 3), ("S2", "B", 3), ("S3", "B", 2)]:
        for k in range(n):
            rows.append({"system_id": system, "category": category, "financial_loss": 1_000.0 * (k + 2)})
    return pd.DataFrame(rows)


def test_system_data_used_when_enough() -> None:
    estimate = estimate_severity(incident_table(), "S1", min_losses=15)
    assert estimate.data_source == "system"
    assert estimate.n_losses == 20
    assert estimate.fallback_notes == []
    assert "S1" in estimate.data_description


def test_falls_back_to_bank_wide_and_says_so() -> None:
    estimate = estimate_severity(incident_table(), "S2", min_losses=15)
    assert estimate.data_source == "bank_wide"
    assert estimate.n_losses == 28
    assert len(estimate.fallback_notes) == 1
    assert "S2" in estimate.fallback_notes[0] and "6 positive losses" in estimate.fallback_notes[0]


def test_falls_back_to_category_before_bank_wide_when_category_requested() -> None:
    estimate = estimate_severity(incident_table(), "S2", category="A", min_losses=15)
    assert estimate.data_source == "category"
    assert estimate.n_losses == 23  # bank-wide category A: 20 + 3
    assert len(estimate.fallback_notes) == 1


def test_category_request_can_still_fall_through_to_bank_wide() -> None:
    estimate = estimate_severity(incident_table(), "S2", category="B", min_losses=15)
    assert estimate.data_source == "bank_wide"
    assert len(estimate.fallback_notes) == 2  # system level and category level both reported


def test_category_request_uses_system_and_category_data_when_enough() -> None:
    estimate = estimate_severity(incident_table(), "S1", category="A", min_losses=15)
    assert estimate.data_source == "system"
    assert "category 'A'" in estimate.data_description


def test_fitted_parameters_match_the_data_used() -> None:
    table = incident_table()
    estimate = estimate_severity(table, "S1", min_losses=15)
    mu, sigma = fit_lognormal(table[table.system_id == "S1"].financial_loss)
    assert (estimate.mu, estimate.sigma) == pytest.approx((mu, sigma))


def test_non_positive_losses_are_excluded_and_counted_honestly() -> None:
    table = incident_table()
    table.loc[table.system_id == "S1", "financial_loss"] = 0.0  # S1 now has no usable losses
    estimate = estimate_severity(table, "S1", min_losses=5)
    assert estimate.data_source == "bank_wide"
    assert estimate.n_losses == 8
    assert "0 positive losses" in estimate.fallback_notes[0]


def test_error_when_even_bank_wide_data_are_insufficient() -> None:
    with pytest.raises(ValueError, match="not enough positive losses"):
        estimate_severity(incident_table(), "S1", min_losses=100)


def test_missing_columns_are_reported() -> None:
    with pytest.raises(ValueError, match="category"):
        estimate_severity(incident_table().drop(columns="category"), "S1", category="A")
