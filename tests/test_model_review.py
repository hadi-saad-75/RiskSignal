"""Regression tests from the technical review (docs/technical_review.md).

They turn the review's independent numerical checks into permanent guards: exact quantile and
Expected Shortfall conventions, the NumPy/SciPy Lognormal parameterisation, aggregation against
naive implementations, coupling of baseline and stress runs, the observation-window guard, the
absence of hardcoded numbers in the agent prompt, and a few cross-module consistency checks.
All random draws use fixed seeds, so every test is deterministic.
"""

import math
import re
import typing
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats

from risksignal.agent.prompts import SYSTEM_PROMPT
from risksignal.api.dependencies import _STATUS_FOR_ERROR_TYPE, Settings, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.storage import init_db
from risksignal.stochastic.frequency import estimate_lambda_from_incidents
from risksignal.stochastic.metrics import compute_metrics, expected_shortfall, value_at_risk
from risksignal.stochastic.schemas import ModelParameters
from risksignal.stochastic.severity import fit_lognormal, lognormal_mean, sample_severities
from risksignal.stochastic.simulation import (
    aggregate_by_year,
    simulate_annual_losses,
    simulate_paired_annual_losses,
)
from risksignal.tools.context import ToolContext
from risksignal.tools.schemas import ToolErrorType
from risksignal.ui.formatting import SECTION_HEADINGS

BASE = ModelParameters(lambda_value=3.8, mu=10.1, sigma=1.5)


def stress_of(lambda_multiplier: float = 1.0, mu_shift: float = 0.0, sigma_multiplier: float = 1.0) -> ModelParameters:
    return ModelParameters(lambda_value=BASE.lambda_value * lambda_multiplier, mu=BASE.mu + mu_shift,
                           sigma=BASE.sigma * sigma_multiplier)


# ----------------------------------------------------------------- quantile and tail conventions


def test_percentiles_and_expected_shortfall_are_exact_on_a_known_sample() -> None:
    losses = np.arange(1.0, 100_001.0)  # 100,000 distinct, equally likely simulated years
    assert value_at_risk(losses, 0.95) == 95_000.0  # smallest x with at least 95% of years <= x
    assert value_at_risk(losses, 0.99) == 99_000.0
    assert expected_shortfall(losses, 0.95) == pytest.approx(97_500.5)  # mean of the worst 5,000 years
    assert expected_shortfall(losses, 0.99) == pytest.approx(99_500.5)  # mean of the worst 1,000 years
    shuffled = np.random.default_rng(0).permutation(losses)
    assert compute_metrics(shuffled) == compute_metrics(losses)


# ----------------------------------------------------------------- NumPy / SciPy parameterisation


def test_numpy_lognormal_parameters_mean_log_space_and_match_scipy() -> None:
    mu, sigma = 10.0, 1.5
    reference = stats.lognorm(s=sigma, scale=math.exp(mu))  # SciPy: shape = sigma, scale = exp(mu)
    assert lognormal_mean(mu, sigma) == pytest.approx(reference.mean(), rel=1e-12)
    assert math.exp(mu) == pytest.approx(reference.median(), rel=1e-12)
    sample = sample_severities(mu, sigma, 400_000, 1)
    assert stats.kstest(sample, reference.cdf).pvalue > 0.001
    assert np.quantile(sample, 0.95) == pytest.approx(reference.ppf(0.95), rel=0.02)
    assert sample.min() > 0


def test_fitted_parameters_equal_the_scipy_maximum_likelihood_fit() -> None:
    losses = sample_severities(10.0, 1.5, 5_000, 2)
    shape, _, scale = stats.lognorm.fit(losses, floc=0)
    mu_hat, sigma_hat = fit_lognormal(losses)
    assert sigma_hat == pytest.approx(shape, rel=1e-6)
    assert mu_hat == pytest.approx(math.log(scale), rel=1e-6)


# ----------------------------------------------------------------- aggregation


def test_vectorised_aggregation_equals_a_naive_loop() -> None:
    rng = np.random.default_rng(3)
    counts = rng.poisson(4.0, 5_000)
    severities = rng.lognormal(10, 1.2, int(counts.sum()))
    naive, position = np.zeros(len(counts)), 0
    for year, n in enumerate(counts):
        naive[year] = severities[position:position + n].sum()
        position += n
    assert np.allclose(aggregate_by_year(counts, severities), naive, rtol=1e-12, atol=0)


def test_engine_matches_an_independent_loop_implementation_in_distribution() -> None:
    lam, mu, sigma = 3.8, 10.1, 1.5
    engine = simulate_annual_losses(lam, mu, sigma, 100_000, 5)
    rng = np.random.default_rng(99)
    reference = np.array([rng.lognormal(mu, sigma, rng.poisson(lam)).sum() for _ in range(20_000)])
    assert stats.ks_2samp(engine, reference).pvalue > 0.001
    assert (engine >= 0).all() and (engine == 0).mean() == pytest.approx(math.exp(-lam), abs=0.005)


# ----------------------------------------------------------------- coupling of baseline and stress


@pytest.mark.parametrize("stress", [stress_of(), stress_of(1.8, 0.2, 1.1), stress_of(0.6, -0.1, 0.9), stress_of(1.0, 0.3)])
def test_paired_baseline_is_bit_identical_to_a_standalone_run(stress: ModelParameters) -> None:
    baseline, _ = simulate_paired_annual_losses(BASE, stress, 20_000, 7)
    assert np.array_equal(baseline, simulate_annual_losses(BASE.lambda_value, BASE.mu, BASE.sigma, 20_000, 7))


def test_a_neutral_scenario_gives_identical_years() -> None:
    baseline, stress = simulate_paired_annual_losses(BASE, stress_of(), 20_000, 1)
    assert np.array_equal(baseline, stress)


@pytest.mark.parametrize("multiplier", [1.01, 1.05, 1.8])
def test_more_incidents_never_reduce_loss_in_any_simulated_year(multiplier: float) -> None:
    baseline, stress = simulate_paired_annual_losses(BASE, stress_of(multiplier, 0.0), 50_000, 11)
    assert (stress >= baseline).all()  # the stressed year contains every baseline incident


@pytest.mark.parametrize("multiplier", [0.5, 0.95])
def test_fewer_incidents_never_increase_loss_in_any_simulated_year(multiplier: float) -> None:
    baseline, stress = simulate_paired_annual_losses(BASE, stress_of(multiplier, 0.0), 50_000, 11)
    assert (stress <= baseline).all()  # thinning keeps a subset of the baseline incidents


def test_a_mild_scenario_can_no_longer_show_a_lower_loss_than_baseline() -> None:
    for seed in range(15):  # with independent random numbers this fails for many seeds (see the review)
        baseline, stress = simulate_paired_annual_losses(BASE, stress_of(1.01), 20_000, seed)
        base_metrics, stress_metrics = compute_metrics(baseline), compute_metrics(stress)
        assert all(getattr(stress_metrics, name) >= getattr(base_metrics, name) for name in type(base_metrics).model_fields)


def test_years_are_strongly_correlated_across_scenarios() -> None:
    baseline, stress = simulate_paired_annual_losses(BASE, stress_of(1.05), 100_000, 3)
    assert np.corrcoef(baseline, stress)[0, 1] > 0.9
    # sanity check of the claim in the docs: merely sharing a seed does NOT couple the runs
    independent = simulate_annual_losses(BASE.lambda_value * 1.05, BASE.mu, BASE.sigma, 100_000, 3)
    assert abs(np.corrcoef(baseline, independent)[0, 1]) < 0.05


@pytest.mark.parametrize("stress", [stress_of(1.8, 0.2, 1.1), stress_of(0.6, -0.1, 0.9), stress_of(1.0, 0.0, 1.3)])
def test_stressed_years_have_the_correct_marginal_distribution(stress: ModelParameters) -> None:
    _, stressed = simulate_paired_annual_losses(BASE, stress, 100_000, 21)
    reference = simulate_annual_losses(stress.lambda_value, stress.mu, stress.sigma, 100_000, 22)  # independent draw
    assert stats.ks_2samp(stressed, reference).pvalue > 0.001
    analytic = stress.lambda_value * lognormal_mean(stress.mu, stress.sigma)
    variance = stress.lambda_value * math.exp(2 * stress.mu + 2 * stress.sigma**2)
    assert abs(stressed.mean() - analytic) < 5 * math.sqrt(variance / 100_000)


def test_paired_simulation_is_deterministic_and_non_negative() -> None:
    first = simulate_paired_annual_losses(BASE, stress_of(1.8, 0.2, 1.1), 10_000, 4)
    again = simulate_paired_annual_losses(BASE, stress_of(1.8, 0.2, 1.1), 10_000, 4)
    assert all(np.array_equal(a, b) for a, b in zip(first, again))
    assert all((losses >= 0).all() and np.isfinite(losses).all() for losses in first)


def test_paired_simulation_respects_the_memory_guard_for_the_larger_lambda() -> None:
    with pytest.raises(ValueError, match="severity draws"):
        simulate_paired_annual_losses(BASE, stress_of(100.0), 1_000_000, 1)


# ----------------------------------------------------------------- observation window guard


def test_incidents_outside_the_window_are_rejected_not_silently_counted() -> None:
    frame = pd.DataFrame({"system_id": ["S"] * 10, "date": [date(2019, 1, 1)] * 5 + [date(2024, 6, 1)] * 5})
    with pytest.raises(ValueError, match="5 incident.*outside the observation window"):
        estimate_lambda_from_incidents(frame, "S", date(2024, 1, 1), date(2024, 12, 31), min_incidents=5)
    inside = frame.iloc[5:]
    assert estimate_lambda_from_incidents(inside, "S", date(2024, 1, 1), date(2024, 12, 31), min_incidents=5).observed_incidents == 5


def test_window_guard_accepts_iso_strings_and_boundaries_and_ignores_frames_without_dates() -> None:
    strings = pd.DataFrame({"system_id": ["S"] * 6, "date": ["2024-01-01", "2024-12-31"] * 3})  # both end days are inside
    assert estimate_lambda_from_incidents(strings, "S", date(2024, 1, 1), date(2024, 12, 31)).observed_incidents == 6
    assert estimate_lambda_from_incidents(strings.drop(columns="date"), "S", date(1990, 1, 1), date(1990, 12, 31)).observed_incidents == 6
    late = strings.assign(date=["2025-01-01"] * 6)
    with pytest.raises(ValueError, match="outside the observation window"):
        estimate_lambda_from_incidents(late, "S", date(2024, 1, 1), date(2024, 12, 31))


# ----------------------------------------------------------------- the agent prompt contains no numbers to copy


def test_system_prompt_has_no_example_values_the_model_could_echo() -> None:
    assert not re.search(r"\d{3,}", SYSTEM_PROMPT)  # no multi-digit example figures
    assert not re.search(r"\d\s*(thousand|million|billion|k\b|m\b|%)", SYSTEM_PROMPT, re.IGNORECASE)
    assert "896" not in SYSTEM_PROMPT


def test_prompt_and_dashboard_use_the_same_section_headings() -> None:
    for heading in SECTION_HEADINGS:
        assert f"- {heading}" in SYSTEM_PROMPT, heading  # the UI can only split what the prompt asks for


# ----------------------------------------------------------------- cross-module consistency


def test_every_tool_error_type_maps_to_an_http_status() -> None:
    assert set(typing.get_args(ToolErrorType)) == set(_STATUS_FOR_ERROR_TYPE)  # a new type cannot silently become a 500


def _health(db_path: Path) -> dict:
    app = create_app()
    ctx = ToolContext(db_path=db_path)
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=db_path, llm_provider="mock")
    return TestClient(app).get("/health").json()


def test_health_is_degraded_for_an_empty_or_unusable_database(tmp_path: Path) -> None:
    (tmp_path / "zero_bytes.db").write_bytes(b"")
    assert _health(tmp_path / "zero_bytes.db")["status"] == "degraded"
    (tmp_path / "not_a_database.db").write_text("this is not sqlite", encoding="utf-8")
    assert _health(tmp_path / "not_a_database.db")["database_available"] is False
    init_db(tmp_path / "schema_only.db")  # tables exist but hold no systems
    assert _health(tmp_path / "schema_only.db")["status"] == "degraded"
    assert not (tmp_path / "missing.db").exists() and _health(tmp_path / "missing.db")["status"] == "degraded"
    assert not (tmp_path / "missing.db").exists()  # checking health never creates a database
