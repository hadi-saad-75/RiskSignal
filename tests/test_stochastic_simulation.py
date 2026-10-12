"""Tests for the Monte Carlo engine and the end-to-end system simulation."""

import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from risksignal.data.generator import DATA_END, DATA_START, generate_atlas_bank
from risksignal.stochastic.metrics import compute_metrics
from risksignal.stochastic.schemas import SimulationResult
from risksignal.stochastic.simulation import (
    aggregate_by_year,
    run_system_simulation,
    simulate_annual_losses,
)

LAM, MU, SIGMA = 3.0, 10.0, 0.8


def test_aggregate_by_year_sums_within_each_year() -> None:
    counts = np.array([2, 0, 3, 0])
    severities = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert aggregate_by_year(counts, severities).tolist() == [3.0, 0.0, 12.0, 0.0]


def test_aggregate_by_year_with_no_incidents_at_all() -> None:
    assert aggregate_by_year(np.zeros(5, dtype=int), np.array([])).tolist() == [0.0] * 5


def test_aggregate_by_year_rejects_inconsistent_lengths() -> None:
    with pytest.raises(ValueError):
        aggregate_by_year(np.array([2, 1]), np.array([1.0, 2.0]))


def test_losses_are_reproducible_for_a_seed() -> None:
    first = simulate_annual_losses(LAM, MU, SIGMA, 5_000, 2024)
    assert np.array_equal(first, simulate_annual_losses(LAM, MU, SIGMA, 5_000, 2024))
    assert not np.array_equal(first, simulate_annual_losses(LAM, MU, SIGMA, 5_000, 2025))


def test_losses_are_non_negative_and_one_per_year() -> None:
    losses = simulate_annual_losses(LAM, MU, SIGMA, 20_000, 1)
    assert losses.shape == (20_000,)
    assert losses.min() >= 0.0
    assert np.all(np.isfinite(losses))


def test_share_of_loss_free_years_matches_poisson_probability_of_zero() -> None:
    n = 200_000
    losses = simulate_annual_losses(LAM, MU, SIGMA, n, 3)
    expected = math.exp(-LAM)  # P(N = 0)
    standard_error = math.sqrt(expected * (1 - expected) / n)
    assert abs((losses == 0.0).mean() - expected) < 5 * standard_error


def test_simulated_mean_matches_closed_form_compound_poisson_mean() -> None:
    n = 200_000
    losses = simulate_annual_losses(LAM, MU, SIGMA, n, 5)
    analytic = LAM * math.exp(MU + SIGMA**2 / 2)  # E[L] = lambda * E[X]
    variance = LAM * math.exp(2 * MU + 2 * SIGMA**2)  # Var[L] = lambda * E[X^2]
    assert abs(losses.mean() - analytic) < 5 * math.sqrt(variance / n)


def test_simulated_variance_matches_closed_form() -> None:
    losses = simulate_annual_losses(LAM, MU, 0.5, 400_000, 6)
    assert losses.var() == pytest.approx(LAM * math.exp(2 * MU + 2 * 0.5**2), rel=0.03)


def test_100k_simulations_are_fast_and_ordered() -> None:
    start = time.perf_counter()
    losses = simulate_annual_losses(LAM, MU, 1.5, 100_000, 7)
    assert time.perf_counter() - start < 5.0
    metrics = compute_metrics(losses)
    assert metrics.median <= metrics.p95 <= metrics.p99
    assert metrics.expected_shortfall_95 >= metrics.p95
    assert metrics.expected_shortfall_99 >= metrics.p99


def test_memory_guard_rejects_absurd_requests() -> None:
    with pytest.raises(ValueError, match="severity draws"):
        simulate_annual_losses(1_000.0, MU, SIGMA, 1_000_000, 1)


def test_more_frequent_or_heavier_tailed_losses_increase_risk() -> None:
    base = compute_metrics(simulate_annual_losses(3.0, MU, 1.0, 100_000, 1))
    more_frequent = compute_metrics(simulate_annual_losses(6.0, MU, 1.0, 100_000, 1))
    heavier = compute_metrics(simulate_annual_losses(3.0, MU, 1.6, 100_000, 1))
    assert more_frequent.p95 > base.p95
    assert heavier.p99 > base.p99


# ----------------------------------------------------------------- end to end on Atlas Bank


@pytest.fixture(scope="module")
def incidents() -> pd.DataFrame:
    return pd.DataFrame([i.model_dump() for i in generate_atlas_bank().incidents])


WINDOW = {"observation_start": DATA_START, "observation_end": DATA_END}


def test_focal_system_run_reports_estimated_inputs_and_sane_outputs(incidents: pd.DataFrame) -> None:
    result = run_system_simulation(incidents, "PAYMENT_ENGINE_01", **WINDOW)
    n_incidents = int((incidents.system_id == "PAYMENT_ENGINE_01").sum())
    assert result.system_id == "PAYMENT_ENGINE_01"
    assert result.frequency_estimation_method == "system_history"
    assert result.observed_incident_count == n_incidents
    assert result.lambda_used == pytest.approx(n_incidents / result.observation_years)
    assert result.severity_data_source == "system"
    assert result.number_of_simulations == 100_000
    assert result.random_seed == 42
    assert result.median_annual_loss <= result.p95 <= result.p99
    assert result.expected_shortfall_95 >= result.p95
    assert result.expected_shortfall_99 >= result.p99
    assert result.mean_annual_loss == pytest.approx(result.analytic_mean_annual_loss, rel=0.03)
    assert "Synthetic" in result.disclaimer


def test_run_is_deterministic_and_seed_sensitive(incidents: pd.DataFrame) -> None:
    first = run_system_simulation(incidents, "PAYMENT_ENGINE_01", seed=5, n_simulations=20_000, **WINDOW)
    again = run_system_simulation(incidents, "PAYMENT_ENGINE_01", seed=5, n_simulations=20_000, **WINDOW)
    other = run_system_simulation(incidents, "PAYMENT_ENGINE_01", seed=6, n_simulations=20_000, **WINDOW)
    assert first == again
    assert first.p99 != other.p99
    assert first.random_seed == 5


def test_override_is_labelled_and_changes_risk(incidents: pd.DataFrame) -> None:
    base = run_system_simulation(incidents, "PAYMENT_ENGINE_01", **WINDOW)
    stressed = run_system_simulation(incidents, "PAYMENT_ENGINE_01", lambda_override=2 * base.lambda_used, **WINDOW)
    assert stressed.frequency_estimation_method == "user_override"
    assert stressed.lambda_used == pytest.approx(2 * base.lambda_used)
    assert stressed.lambda_historical == pytest.approx(base.lambda_used)
    assert (stressed.severity_mu, stressed.severity_sigma) == (base.severity_mu, base.severity_sigma)
    assert stressed.mean_annual_loss > 1.8 * base.mean_annual_loss


def test_sparse_system_fallbacks_are_visible_in_the_result(incidents: pd.DataFrame) -> None:
    result = run_system_simulation(incidents, "PRIVILEGED_ACCESS_01", **WINDOW)
    assert result.observed_incident_count == 2
    assert result.frequency_estimation_method == "bank_wide_per_system_average"
    assert result.severity_data_source == "bank_wide"
    assert result.severity_fallback_notes
    assert "bank-wide" in result.frequency_note


def test_category_model_uses_category_data_consistently(incidents: pd.DataFrame) -> None:
    result = run_system_simulation(incidents, "PAYMENT_ENGINE_01", category="third_party_failure", **WINDOW)
    assert result.incident_category == "third_party_failure"
    assert result.severity_data_source == "category"
    count = int(((incidents.system_id == "PAYMENT_ENGINE_01") & (incidents.category == "third_party_failure")).sum())
    assert result.observed_incident_count == count


def test_result_is_compact_and_serialisable(incidents: pd.DataFrame) -> None:
    result = run_system_simulation(incidents, "PAYMENT_ENGINE_01", **WINDOW)
    payload = result.model_dump_json()
    assert len(payload) < 10_000  # summary and histogram only, not 100,000 values
    assert SimulationResult.model_validate_json(payload) == result
    assert sum(result.histogram.counts) + result.histogram.overflow_count == result.number_of_simulations
    assert run_system_simulation(incidents, "PAYMENT_ENGINE_01", histogram_bins=None, **WINDOW).histogram is None


def test_default_window_comes_from_incident_dates(incidents: pd.DataFrame) -> None:
    explicit = run_system_simulation(incidents, "PAYMENT_ENGINE_01", n_simulations=1_000, **WINDOW)
    implied = run_system_simulation(incidents, "PAYMENT_ENGINE_01", n_simulations=1_000)
    assert implied.observation_years <= explicit.observation_years
    assert implied.lambda_used >= explicit.lambda_used


def test_stochastic_package_does_not_depend_on_llm_ui_or_data_layers() -> None:
    package = Path(__file__).resolve().parents[1] / "src" / "risksignal" / "stochastic"
    forbidden = ("anthropic", "risksignal.agent", "risksignal.api", "risksignal.ui", "risksignal.tools",
                 "risksignal.data", "fastapi", "streamlit", "sqlite3")
    for source in package.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
        assert not [i for i in imports if any(name in i for name in forbidden)], source.name
