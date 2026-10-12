"""Tests for the Poisson frequency model."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from risksignal.stochastic.frequency import (
    DAYS_PER_YEAR,
    estimate_lambda_from_incidents,
    observation_years,
    simulate_incident_counts,
)

START, END = date(2021, 1, 1), date(2025, 12, 31)  # 1826 days
YEARS = 1826 / DAYS_PER_YEAR


def incident_table(per_system: dict[str, int]) -> pd.DataFrame:
    rows = [{"system_id": s, "date": START} for s, n in per_system.items() for _ in range(n)]
    return pd.DataFrame(rows, columns=["system_id", "date"])


def test_observation_years_counts_both_end_dates() -> None:
    assert observation_years(date(2024, 1, 1), date(2024, 1, 1)) == pytest.approx(1 / DAYS_PER_YEAR)
    assert observation_years(START, END) == pytest.approx(YEARS)
    with pytest.raises(ValueError):
        observation_years(END, START)


def test_lambda_is_count_divided_by_years() -> None:
    table = incident_table({"S1": 10, "S2": 20})
    estimate = estimate_lambda_from_incidents(table, "S1", START, END)
    assert estimate.lambda_used == pytest.approx(10 / YEARS)
    assert estimate.method == "system_history"
    assert estimate.observed_incidents == 10
    assert estimate.observation_years == pytest.approx(YEARS)


def test_insufficient_data_uses_labelled_bank_wide_average() -> None:
    table = incident_table({"S1": 2, "S2": 20, "S3": 10})
    estimate = estimate_lambda_from_incidents(table, "S1", START, END)
    assert estimate.method == "bank_wide_per_system_average"
    assert estimate.lambda_used == pytest.approx(32 / YEARS / 3)
    assert estimate.lambda_historical == pytest.approx(2 / YEARS)
    assert "only 2 incidents" in estimate.note


def test_bank_wide_average_can_use_explicit_system_count() -> None:
    table = incident_table({"S1": 2, "S2": 20, "S3": 10})
    estimate = estimate_lambda_from_incidents(table, "S1", START, END, n_systems=4)
    assert estimate.lambda_used == pytest.approx(32 / YEARS / 4)


def test_system_with_no_incidents_falls_back_instead_of_zero() -> None:
    table = incident_table({"S2": 20, "S3": 10})
    estimate = estimate_lambda_from_incidents(table, "S_NEW", START, END)
    assert estimate.method == "bank_wide_per_system_average"
    assert estimate.observed_incidents == 0
    assert estimate.lambda_used > 0


def test_min_incidents_threshold_is_respected() -> None:
    table = incident_table({"S1": 4, "S2": 20})
    assert estimate_lambda_from_incidents(table, "S1", START, END, min_incidents=4).method == "system_history"
    assert estimate_lambda_from_incidents(table, "S1", START, END, min_incidents=5).method != "system_history"


def test_user_override_wins_and_keeps_history_for_comparison() -> None:
    table = incident_table({"S1": 10, "S2": 20})
    estimate = estimate_lambda_from_incidents(table, "S1", START, END, lambda_override=7.5)
    assert estimate.lambda_used == 7.5
    assert estimate.method == "user_override"
    assert estimate.lambda_historical == pytest.approx(10 / YEARS)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
def test_invalid_override_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        estimate_lambda_from_incidents(incident_table({"S1": 10}), "S1", START, END, lambda_override=bad)


def test_no_history_at_all_is_an_error_without_override() -> None:
    empty = incident_table({})
    with pytest.raises(ValueError, match="lambda_override"):
        estimate_lambda_from_incidents(empty, "S1", START, END)
    assert estimate_lambda_from_incidents(empty, "S1", START, END, lambda_override=2.0).lambda_used == 2.0


def test_simulated_counts_have_requested_mean_and_variance() -> None:
    lam, n = 4.5, 200_000
    counts = simulate_incident_counts(lam, n, np.random.default_rng(1))
    standard_error = np.sqrt(lam / n)
    assert abs(counts.mean() - lam) < 5 * standard_error
    assert counts.var() == pytest.approx(lam, rel=0.03)  # Poisson: variance equals the mean


def test_simulated_counts_are_non_negative_integers() -> None:
    counts = simulate_incident_counts(3.0, 10_000, 5)
    assert counts.dtype.kind == "i"
    assert counts.min() >= 0


def test_counts_are_reproducible_for_a_seed() -> None:
    first = simulate_incident_counts(3.0, 1_000, 123)
    assert np.array_equal(first, simulate_incident_counts(3.0, 1_000, 123))
    assert not np.array_equal(first, simulate_incident_counts(3.0, 1_000, 124))


def test_invalid_count_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        simulate_incident_counts(-1.0, 10, 1)
    with pytest.raises(ValueError):
        simulate_incident_counts(1.0, 0, 1)
