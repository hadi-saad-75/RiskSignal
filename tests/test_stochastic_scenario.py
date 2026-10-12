"""Tests for the stress scenario engine."""

import math

import pandas as pd
import pytest
from pydantic import ValidationError

from risksignal.data.generator import DATA_END, DATA_START, generate_atlas_bank
from risksignal.stochastic.frequency import simulate_incident_counts
from risksignal.stochastic.schemas import (
    LossMetrics,
    ModelParameters,
    Scenario,
    ScenarioComparison,
)
from risksignal.stochastic.scenario import (
    PREDEFINED_SCENARIOS,
    SHARED_VENDOR_OUTAGE,
    apply_scenario,
    compare_metrics,
    compare_scenario,
    get_predefined_scenario,
    make_user_scenario,
    run_scenario_analysis,
)
from risksignal.stochastic.simulation import (
    analytic_mean_annual_loss,
    build_baseline_model,
    run_system_simulation,
)

FOCAL = "PAYMENT_ENGINE_01"
WINDOW = {"observation_start": DATA_START, "observation_end": DATA_END}
BASE = ModelParameters(lambda_value=2.0, mu=10.0, sigma=1.0)


@pytest.fixture(scope="module")
def incidents() -> pd.DataFrame:
    return pd.DataFrame([i.model_dump() for i in generate_atlas_bank().incidents])


# ----------------------------------------------------------------- scenario object and parameters


def test_scenario_defaults_are_neutral() -> None:
    scenario = Scenario(scenario_id="S", name="n", description="d")
    assert (scenario.lambda_multiplier, scenario.severity_mu_shift, scenario.severity_sigma_multiplier) == (1.0, 0.0, 1.0)
    assert scenario.assumption_notes == []


@pytest.mark.parametrize(
    "field, value",
    [
        ("lambda_multiplier", 0.0), ("lambda_multiplier", -1.0), ("lambda_multiplier", float("nan")),
        ("lambda_multiplier", float("inf")), ("lambda_multiplier", 1_000.0),
        ("severity_sigma_multiplier", 0.0), ("severity_sigma_multiplier", -0.5), ("severity_sigma_multiplier", 50.0),
        ("severity_mu_shift", float("nan")), ("severity_mu_shift", 100.0), ("severity_mu_shift", -100.0),
    ],
)
def test_invalid_scenario_numbers_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        Scenario(scenario_id="S", name="n", description="d", **{field: value})


def test_multiplier_of_one_leaves_lambda_unchanged() -> None:
    stressed = apply_scenario(BASE, make_user_scenario(lambda_multiplier=1.0))
    assert stressed.lambda_value == BASE.lambda_value  # exactly, not approximately
    assert stressed == BASE  # and mu, sigma too, because the other defaults are neutral


def test_apply_scenario_formula_with_known_numbers() -> None:
    stressed = apply_scenario(BASE, make_user_scenario(1.8, 0.2, 1.1))
    assert stressed.lambda_value == pytest.approx(3.6)
    assert stressed.mu == pytest.approx(10.2)
    assert stressed.sigma == pytest.approx(1.1)


def test_apply_scenario_does_not_modify_the_baseline() -> None:
    before = BASE.model_copy()
    apply_scenario(BASE, make_user_scenario(3.0, 1.0, 2.0))
    assert BASE == before


def test_each_parameter_is_changed_independently() -> None:
    assert apply_scenario(BASE, make_user_scenario(lambda_multiplier=1.5)) == ModelParameters(
        lambda_value=3.0, mu=10.0, sigma=1.0)
    assert apply_scenario(BASE, make_user_scenario(severity_mu_shift=-0.5)) == ModelParameters(
        lambda_value=2.0, mu=9.5, sigma=1.0)
    assert apply_scenario(BASE, make_user_scenario(severity_sigma_multiplier=1.2)) == ModelParameters(
        lambda_value=2.0, mu=10.0, sigma=1.2)


# ----------------------------------------------------------------- predefined and user scenarios


def test_predefined_scenario_is_labelled_illustrative_and_not_calibrated() -> None:
    scenario = get_predefined_scenario("SHARED_VENDOR_OUTAGE")
    assert scenario is SHARED_VENDOR_OUTAGE
    assert (scenario.lambda_multiplier, scenario.severity_mu_shift, scenario.severity_sigma_multiplier) == (1.8, 0.20, 1.10)
    assert scenario.provenance == "predefined_illustrative"
    notes = " ".join(scenario.assumption_notes).lower()
    assert "illustrative" in notes and "not empirically calibrated" in notes
    assert "dependency graph" in notes  # states that no causal link is derived from the graph


def test_unknown_predefined_scenario_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="SHARED_VENDOR_OUTAGE"):
        get_predefined_scenario("NO_SUCH_SCENARIO")
    assert set(PREDEFINED_SCENARIOS) == {"SHARED_VENDOR_OUTAGE"}


def test_user_scenario_carries_the_given_numbers() -> None:
    scenario = make_user_scenario(1.5, 0.0, 1.2, name="my test", scenario_id="MINE")
    assert (scenario.scenario_id, scenario.name) == ("MINE", "my test")
    assert (scenario.lambda_multiplier, scenario.severity_mu_shift, scenario.severity_sigma_multiplier) == (1.5, 0.0, 1.2)
    assert scenario.provenance == "user_supplied"
    assert "1.5" in scenario.description and "1.2" in scenario.description


def test_user_scenario_rejects_bad_numbers() -> None:
    with pytest.raises(ValidationError):
        make_user_scenario(lambda_multiplier=-2.0)


# ----------------------------------------------------------------- frequency effect


def test_larger_lambda_means_more_incidents_on_average() -> None:
    stressed = apply_scenario(BASE, make_user_scenario(lambda_multiplier=1.5))
    assert stressed.lambda_value > BASE.lambda_value
    n = 200_000
    base_counts = simulate_incident_counts(BASE.lambda_value, n, 11)
    stress_counts = simulate_incident_counts(stressed.lambda_value, n, 11)
    assert stress_counts.mean() > base_counts.mean()
    assert stress_counts.mean() == pytest.approx(3.0, abs=0.05)


def test_analytic_mean_scales_exactly_as_the_formula_says() -> None:
    m_lambda, delta, m_sigma = 1.8, 0.2, 1.1
    stressed = apply_scenario(BASE, make_user_scenario(m_lambda, delta, m_sigma))
    ratio = analytic_mean_annual_loss(stressed) / analytic_mean_annual_loss(BASE)
    assert ratio == pytest.approx(m_lambda * math.exp(delta + BASE.sigma**2 * (m_sigma**2 - 1) / 2))


# ----------------------------------------------------------------- comparison arithmetic


def test_differences_are_stress_minus_baseline_and_percent_of_baseline() -> None:
    baseline = LossMetrics(mean=100, median=80, p95=300, p99=500, expected_shortfall_95=400, expected_shortfall_99=700)
    stress = LossMetrics(mean=150, median=60, p95=450, p99=500, expected_shortfall_95=800, expected_shortfall_99=1400)
    absolute, percent = compare_metrics(baseline, stress)
    assert absolute.mean == 50 and absolute.median == -20 and absolute.p99 == 0
    assert percent.mean == pytest.approx(50.0)
    assert percent.median == pytest.approx(-25.0)
    assert percent.p99 == pytest.approx(0.0)
    assert percent.expected_shortfall_99 == pytest.approx(100.0)


def test_percentage_is_undefined_when_the_baseline_is_zero() -> None:
    zero = LossMetrics(mean=0, median=0, p95=0, p99=0, expected_shortfall_95=0, expected_shortfall_99=0)
    stress = LossMetrics(mean=5, median=0, p95=1, p99=2, expected_shortfall_95=3, expected_shortfall_99=4)
    absolute, percent = compare_metrics(zero, stress)
    assert absolute.mean == 5
    assert percent.mean is None and percent.median is None and percent.p99 is None


# ----------------------------------------------------------------- end to end on Atlas Bank


def test_neutral_scenario_reproduces_the_baseline_exactly(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, make_user_scenario(), **WINDOW)
    assert result.stress_parameters == result.baseline_parameters
    assert result.stress_metrics == result.baseline_metrics
    assert all(v == 0 for v in result.absolute_differences.model_dump().values())
    assert all(v == 0 for v in result.percentage_differences.model_dump().values())
    assert result.parameter_changes.lambda_absolute == 0 and result.parameter_changes.mu_absolute == 0


def test_comparison_is_deterministic_and_seed_sensitive(incidents: pd.DataFrame) -> None:
    kwargs = {"n_simulations": 20_000, **WINDOW}
    first = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, seed=9, **kwargs)
    again = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, seed=9, **kwargs)
    other = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, seed=10, **kwargs)
    assert first == again
    assert first.stress_metrics.p99 != other.stress_metrics.p99
    assert first.random_seed == 9


def test_baseline_and_stress_are_clearly_separated(incidents: pd.DataFrame) -> None:
    comparison = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, **WINDOW)
    baseline_model = build_baseline_model(incidents, FOCAL, **WINDOW)
    standalone = run_system_simulation(incidents, FOCAL, **WINDOW)

    # The baseline side is untouched by the scenario: same parameters and metrics as a plain baseline run.
    assert comparison.baseline_parameters == baseline_model.parameters
    assert comparison.baseline_model == baseline_model
    assert comparison.baseline_metrics.p95 == standalone.p95
    assert comparison.baseline_metrics.expected_shortfall_99 == standalone.expected_shortfall_99

    # The stress side is a different object, derived only through the scenario.
    assert comparison.stress_parameters == apply_scenario(comparison.baseline_parameters, SHARED_VENDOR_OUTAGE)
    assert comparison.stress_parameters != comparison.baseline_parameters
    assert comparison.stress_metrics != comparison.baseline_metrics
    assert comparison.scenario.scenario_id == "SHARED_VENDOR_OUTAGE"

    # Distinct, separately named fields in the serialised output.
    payload = comparison.model_dump()
    assert {"baseline_parameters", "stress_parameters", "baseline_metrics", "stress_metrics",
            "absolute_differences", "percentage_differences"} <= set(payload)


def test_predefined_scenario_raises_all_risk_metrics(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, **WINDOW)
    assert all(v > 0 for v in result.absolute_differences.model_dump().values())
    assert all(v > 0 for v in result.percentage_differences.model_dump().values())
    assert result.stress_metrics.median <= result.stress_metrics.p95 <= result.stress_metrics.p99
    assert result.stress_metrics.expected_shortfall_95 >= result.stress_metrics.p95
    assert result.stress_metrics.expected_shortfall_99 >= result.stress_metrics.p99
    assert result.parameter_changes.lambda_percent == pytest.approx(80.0)
    assert result.parameter_changes.sigma_percent == pytest.approx(10.0)
    assert result.parameter_changes.mu_absolute == pytest.approx(0.20)


def test_simulated_stress_mean_is_close_to_closed_form(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, **WINDOW)
    assert result.stress_metrics.mean == pytest.approx(result.stress_analytic_mean_annual_loss, rel=0.05)
    assert result.baseline_metrics.mean == pytest.approx(result.baseline_analytic_mean_annual_loss, rel=0.05)


def test_user_scenario_example_from_the_brief(incidents: pd.DataFrame) -> None:
    scenario = make_user_scenario(lambda_multiplier=1.5, severity_sigma_multiplier=1.2)
    result = run_scenario_analysis(incidents, FOCAL, scenario, **WINDOW)
    base, stress = result.baseline_parameters, result.stress_parameters
    assert stress.lambda_value == pytest.approx(1.5 * base.lambda_value)
    assert stress.sigma == pytest.approx(1.2 * base.sigma)
    assert stress.mu == base.mu
    assert result.stress_metrics.p99 > result.baseline_metrics.p99


def test_heavier_tail_alone_raises_tail_metrics_more_than_the_median(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, make_user_scenario(severity_sigma_multiplier=1.3), **WINDOW)
    changes = result.percentage_differences
    assert changes.expected_shortfall_99 > changes.median


def test_lambda_override_baseline_is_user_supplied_and_gets_stressed(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, make_user_scenario(2.0), lambda_override=5.0, **WINDOW)
    assert result.baseline_model.frequency.method == "user_override"
    assert result.baseline_parameters.lambda_value == 5.0
    assert result.stress_parameters.lambda_value == 10.0


def test_sparse_system_provenance_is_carried_into_the_comparison(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, "PRIVILEGED_ACCESS_01", SHARED_VENDOR_OUTAGE, **WINDOW)
    assert result.baseline_model.frequency.method == "bank_wide_per_system_average"
    assert result.baseline_model.severity.data_source == "bank_wide"


def test_compare_scenario_accepts_a_prebuilt_model_and_optional_histograms(incidents: pd.DataFrame) -> None:
    model = build_baseline_model(incidents, FOCAL, **WINDOW)
    with_hist = compare_scenario(model, SHARED_VENDOR_OUTAGE, n_simulations=10_000)
    without = compare_scenario(model, SHARED_VENDOR_OUTAGE, n_simulations=10_000, histogram_bins=None)
    assert with_hist.baseline_histogram is not None and with_hist.stress_histogram is not None
    assert without.baseline_histogram is None and without.stress_histogram is None
    assert without.stress_metrics == with_hist.stress_metrics


def test_comparison_is_compact_serialisable_and_disclaims(incidents: pd.DataFrame) -> None:
    result = run_scenario_analysis(incidents, FOCAL, SHARED_VENDOR_OUTAGE, **WINDOW)
    payload = result.model_dump_json()
    assert len(payload) < 20_000
    assert ScenarioComparison.model_validate_json(payload) == result
    assert "not empirically calibrated" in result.disclaimer
    assert result.number_of_simulations == 100_000


def test_scenario_module_has_no_llm_or_ui_imports() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src" / "risksignal" / "stochastic" / "scenario.py"
    imports = [l for l in source.read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from "))]
    forbidden = ("anthropic", "risksignal.agent", "risksignal.api", "risksignal.ui", "risksignal.tools", "risksignal.data")
    assert not [i for i in imports if any(name in i for name in forbidden)]
