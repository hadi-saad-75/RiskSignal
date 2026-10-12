"""Tests for the deterministic tool layer."""

import ast
import json
from datetime import date
from pathlib import Path
from unittest import mock

import pytest

from risksignal.data.generator import DATA_END, DATA_START, generate_atlas_bank
from risksignal.data.schemas import AtlasBankDataset
from risksignal.data.storage import save_atlas_bank
from risksignal.graph import queries as graph_queries
from risksignal.graph.builder import load_graph
from risksignal.stochastic import scenario as scenario_module
from risksignal.stochastic.scenario import SHARED_VENDOR_OUTAGE
from risksignal.stochastic.simulation import run_system_simulation
from risksignal.tools.context import ToolContext
from risksignal.tools.control_tools import get_controls
from risksignal.tools.graph_tools import get_dependencies
from risksignal.tools.incident_tools import get_recent_incidents, window_start
from risksignal.tools.kri_tools import get_kri_history
from risksignal.tools.schemas import ToolError
from risksignal.tools.simulation_tools import compare_baseline_and_stress, run_loss_simulation
from risksignal.tools.system_tools import get_system_profile, list_systems

FOCAL = "PAYMENT_ENGINE_01"
TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "risksignal" / "tools"

DATA_TOOLS = [get_system_profile, get_recent_incidents, get_kri_history, get_controls, get_dependencies]
ALL_TOOLS = DATA_TOOLS + [run_loss_simulation]  # compare_baseline_and_stress needs an extra argument


@pytest.fixture(scope="module")
def dataset() -> AtlasBankDataset:
    return generate_atlas_bank()


@pytest.fixture(scope="module")
def ctx(dataset: AtlasBankDataset, tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(dataset, tmp_path_factory.mktemp("tools_db")))


def call_any(tool, ctx: ToolContext, system_id: object):
    """Call any tool with just a system ID (adding a scenario for the comparison tool)."""
    if tool is compare_baseline_and_stress:
        return tool(ctx, system_id, "SHARED_VENDOR_OUTAGE")
    return tool(ctx, system_id)


EVERY_TOOL = ALL_TOOLS + [compare_baseline_and_stress]


# ----------------------------------------------------------------- get_system_profile


def test_list_systems_returns_all_systems_sorted(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = list_systems(ctx)
    assert result.ok and result.data_kind == "observed_synthetic_data"
    assert [s.system_id for s in result.systems] == sorted(s.system_id for s in dataset.systems)
    focal = next(s for s in result.systems if s.system_id == FOCAL)
    assert (focal.name, focal.criticality, focal.primary_process_name) == ("Payment Engine 01", "critical", "International Payments")
    assert list_systems(ToolContext(db_path=ctx.db_path.parent / "missing.db")).error_type == "data_unavailable"


def test_system_profile_contents(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = get_system_profile(ctx, FOCAL)
    assert result.ok and result.data_kind == "observed_synthetic_data"
    assert (result.system.system_id, result.system.name, result.system.criticality) == (
        FOCAL, "Payment Engine 01", "critical")
    assert result.primary_process.name == "International Payments"
    meta = result.metadata
    assert meta.total_incidents_recorded == sum(i.system_id == FOCAL for i in dataset.incidents)
    assert meta.number_of_controls == sum(c.system_id == FOCAL for c in dataset.controls) == 4
    assert meta.kris_tracked == sorted(meta.kris_tracked) and len(meta.kris_tracked) == 5
    assert (meta.data_window_start, meta.data_window_end) == (DATA_START, DATA_END)
    assert "Synthetic" in result.notice and "Synthetic" in meta.data_source


# ----------------------------------------------------------------- get_recent_incidents


def test_window_start_is_calendar_months_back() -> None:
    assert window_start(date(2026, 9, 30), 12) == date(2025, 9, 30)
    assert window_start(date(2026, 9, 30), 1) == date(2026, 8, 30)
    assert window_start(date(2026, 3, 31), 1) == date(2026, 2, 28)


def test_recent_incidents_match_the_database_and_counts_add_up(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = get_recent_incidents(ctx, FOCAL, months=12)
    cutoff = date(2025, 9, 30)
    expected = [i for i in dataset.incidents if i.system_id == FOCAL and i.date > cutoff]
    assert [i.incident_id for i in result.incidents] == [i.incident_id for i in expected]
    assert result.incidents == sorted(result.incidents, key=lambda i: (i.date, i.incident_id))
    assert result.window_start_exclusive == cutoff and result.window_end_inclusive == DATA_END

    counts = result.counts
    assert counts.total == len(expected) >= 3
    assert sum(counts.by_category.values()) == sum(counts.by_severity.values()) == counts.total
    assert counts.deployment_keyword_matches == sum("deployment" in i.description.lower() for i in expected) >= 2
    assert counts.total_financial_loss == pytest.approx(sum(i.financial_loss for i in expected))
    assert all(i.mentions_deployment == ("deployment" in i.description.lower()) for i in result.incidents)


def test_longer_window_returns_the_full_history(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = get_recent_incidents(ctx, FOCAL, months=60)
    assert result.counts.total == sum(i.system_id == FOCAL for i in dataset.incidents)


def test_empty_window_is_a_valid_empty_result(ctx: ToolContext) -> None:
    quiet = [s for s in ("CASH_FORECAST_01", "KYC_DOCUMENT_STORE_01", "MESSAGING_HUB_01", "SANCTIONS_SCREENING_01")
             if get_recent_incidents(ctx, s, months=1).counts.total == 0]
    assert quiet, "expected at least one system without incidents in the last month"
    result = get_recent_incidents(ctx, quiet[0], months=1)
    assert result.ok and result.incidents == [] and result.counts.total == 0 and result.counts.by_category == {}


# ----------------------------------------------------------------- get_kri_history


def test_kri_history_grouped_by_kri_with_correct_statistics(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = get_kri_history(ctx, FOCAL, months=12)
    assert [s.kri_name for s in result.series] == sorted(
        {"failed_deployment_rate", "system_downtime_minutes", "near_miss_count",
         "control_exception_count", "vendor_incident_count"})
    for series in result.series:
        values = [k.value for k in dataset.kri_observations if k.system_id == FOCAL and k.kri_name == series.kri_name]
        assert [p.value for p in series.observations] == values[-12:]
        assert len(series.observations) == 12
        assert series.latest_value == values[-1]
        assert series.window_mean == pytest.approx(sum(values[-12:]) / 12)
        assert (series.window_min, series.window_max) == (min(values[-12:]), max(values[-12:]))
        previous_mean = sum(values[-24:-12]) / 12
        assert series.previous_window_mean == pytest.approx(previous_mean)
        assert series.change_vs_previous_window_percent == pytest.approx(
            100 * (series.window_mean - previous_mean) / previous_mean)


def test_focal_deployment_kri_is_higher_than_in_the_previous_window(ctx: ToolContext) -> None:
    series = {s.kri_name: s for s in get_kri_history(ctx, FOCAL, months=12).series}
    assert series["failed_deployment_rate"].change_vs_previous_window_percent > 0


def test_kri_history_without_enough_history_has_no_comparison(ctx: ToolContext) -> None:
    result = get_kri_history(ctx, FOCAL, months=40)  # 40 + 40 > 60 observations
    assert all(len(s.observations) == 40 for s in result.series)
    assert all(s.previous_window_mean is None and s.change_vs_previous_window_percent is None for s in result.series)


def test_systems_without_vendors_have_no_vendor_kri(ctx: ToolContext) -> None:
    names = [s.kri_name for s in get_kri_history(ctx, "REG_REPORTING_ENGINE_01").series]
    assert "vendor_incident_count" not in names and len(names) == 4


# ----------------------------------------------------------------- get_controls


def test_controls_match_the_database(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    result = get_controls(ctx, FOCAL)
    expected = [c for c in dataset.controls if c.system_id == FOCAL]
    assert [c.control_id for c in result.controls] == [c.control_id for c in expected]
    assert result.overdue_control_ids == [c.control_id for c in expected if c.review_status == "overdue"]
    assert len(result.overdue_control_ids) == 1
    assert result.due_control_ids == [c.control_id for c in expected if c.review_status == "due"]
    assert sum(result.counts_by_review_status.values()) == len(expected)
    for record, control in zip(result.controls, expected):
        assert record.days_since_last_review == (DATA_END - control.last_review_date).days
        assert record.review_status == control.review_status and record.description
    assert result.as_of_date == DATA_END and result.data_kind == "observed_synthetic_data"


# ----------------------------------------------------------------- get_dependencies (delegation)


def test_dependencies_come_from_the_graph_module_functions(ctx: ToolContext) -> None:
    names = ["get_system_dependencies", "get_supported_processes", "get_controls_for_system",
             "get_shared_vendors", "get_related_systems"]
    spies = {n: mock.patch(f"risksignal.tools.graph_tools.{n}", wraps=getattr(graph_queries, n)) for n in names}
    started = {n: p.start() for n, p in spies.items()}
    try:
        result = get_dependencies(ctx, FOCAL)
    finally:
        for p in spies.values():
            p.stop()
    for name, spy in started.items():
        spy.assert_called_once_with(ctx.graph, FOCAL)

    assert result.vendors == graph_queries.get_system_dependencies(ctx.graph, FOCAL).vendors
    assert result.related_systems == graph_queries.get_related_systems(ctx.graph, FOCAL).related_systems
    assert result.controls == graph_queries.get_controls_for_system(ctx.graph, FOCAL)


def test_dependencies_show_vendors_processes_controls_and_the_shared_vendor(ctx: ToolContext) -> None:
    result = get_dependencies(ctx, FOCAL)
    assert {v.vendor_id for v in result.vendors} == {"V02", "V04"}
    assert [p.name for p in result.supported_processes] == ["International Payments"]
    assert len(result.controls.controls) == 4
    v04 = next(s for s in result.shared_vendors if s.vendor.vendor_id == "V04")
    assert [o.system_id for o in v04.other_systems] == ["PAYMENT_ENGINE_02"]
    related = {r.system.system_id: r for r in result.related_systems}
    assert related["PAYMENT_ENGINE_02"].relationships[0].kind == "shared_vendor"
    assert result.upstream_systems and result.indirect_vendors


def test_graph_is_built_once_by_the_graph_module(ctx: ToolContext, dataset: AtlasBankDataset, tmp_path: Path) -> None:
    fresh = ToolContext(db_path=save_atlas_bank(dataset, tmp_path))
    with mock.patch("risksignal.tools.context.load_graph", wraps=load_graph) as spy:
        get_dependencies(fresh, FOCAL)
        get_dependencies(fresh, "PAYMENT_ENGINE_02")
    spy.assert_called_once_with(fresh.db_path)


# ----------------------------------------------------------------- simulation (delegation)


def test_loss_simulation_calls_the_stochastic_engine_and_reports_its_numbers(ctx: ToolContext) -> None:
    with mock.patch("risksignal.tools.simulation_tools.run_system_simulation", wraps=run_system_simulation) as spy:
        result = run_loss_simulation(ctx, FOCAL, number_of_simulations=20_000, random_seed=7)
    spy.assert_called_once()
    args, kwargs = spy.call_args
    assert args[1] == FOCAL
    assert kwargs == {"n_simulations": 20_000, "seed": 7, "observation_start": DATA_START,
                      "observation_end": DATA_END, "n_systems": 20}

    direct = run_system_simulation(ctx.incidents_frame(), FOCAL, n_simulations=20_000, seed=7,
                                   observation_start=DATA_START, observation_end=DATA_END, n_systems=20)
    metrics = result.simulation_results.metrics
    assert (metrics.mean, metrics.median, metrics.p95, metrics.p99) == (
        direct.mean_annual_loss, direct.median_annual_loss, direct.p95, direct.p99)
    assert metrics.expected_shortfall_95 == direct.expected_shortfall_95
    assert metrics.expected_shortfall_99 == direct.expected_shortfall_99
    assert result.simulation_results.analytic_mean_annual_loss == direct.analytic_mean_annual_loss


def test_loss_simulation_separates_observed_basis_assumptions_and_outputs(ctx: ToolContext) -> None:
    result = run_loss_simulation(ctx, FOCAL)
    assert result.ok and result.data_kind == "modelled_output" and "Modelled output" in result.notice
    basis, assumptions, outputs = result.observed_basis, result.model_assumptions, result.simulation_results
    assert basis.observed_incident_count == get_system_profile(ctx, FOCAL).metadata.total_incidents_recorded
    assert basis.severity_data_source == "system" and basis.severity_losses_used == basis.observed_incident_count
    assert assumptions.lambda_source == "system_history"
    assert assumptions.lambda_used == pytest.approx(basis.observed_incident_count / basis.observation_years)
    assert (assumptions.number_of_simulations, assumptions.random_seed) == (100_000, 42)
    assert "Poisson" in assumptions.frequency_model and "Lognormal" in assumptions.severity_model
    text = " ".join(assumptions.assumption_statements).lower()
    assert "illustrative" in text and "independent" in text and "not propagated" in text
    assert outputs.metrics.median <= outputs.metrics.p95 <= outputs.metrics.p99
    assert outputs.metrics.expected_shortfall_95 >= outputs.metrics.p95
    assert outputs.metrics.mean == pytest.approx(outputs.analytic_mean_annual_loss, rel=0.05)
    assert len(outputs.histogram.counts) == 50 and len(result.model_dump_json()) < 10_000


def test_loss_simulation_is_deterministic_and_seed_sensitive(ctx: ToolContext) -> None:
    first = run_loss_simulation(ctx, FOCAL, 10_000, 3)
    assert first == run_loss_simulation(ctx, FOCAL, 10_000, 3)
    assert first.simulation_results != run_loss_simulation(ctx, FOCAL, 10_000, 4).simulation_results


def test_fallbacks_are_reported_for_a_sparse_system(ctx: ToolContext) -> None:
    result = run_loss_simulation(ctx, "PRIVILEGED_ACCESS_01", 5_000)
    assert result.model_assumptions.lambda_source == "bank_wide_per_system_average"
    assert result.observed_basis.severity_data_source == "bank_wide"
    assert result.observed_basis.severity_fallback_notes


def test_scenario_tool_calls_the_scenario_engine(ctx: ToolContext) -> None:
    with mock.patch("risksignal.tools.simulation_tools.run_scenario_analysis",
                    wraps=scenario_module.run_scenario_analysis) as spy:
        result = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE", 20_000, 9)
    spy.assert_called_once()
    args, kwargs = spy.call_args
    assert args[1] == FOCAL and args[2] is SHARED_VENDOR_OUTAGE
    assert kwargs["n_simulations"] == 20_000 and kwargs["seed"] == 9 and kwargs["n_systems"] == 20

    direct = scenario_module.run_scenario_analysis(
        ctx.incidents_frame(), FOCAL, SHARED_VENDOR_OUTAGE, n_simulations=20_000, seed=9,
        observation_start=DATA_START, observation_end=DATA_END, n_systems=20)
    out = result.simulation_results
    assert out.baseline_metrics == direct.baseline_metrics
    assert out.stress_metrics == direct.stress_metrics
    assert out.absolute_differences == direct.absolute_differences
    assert out.percentage_differences == direct.percentage_differences


def test_scenario_result_labels_stress_assumptions_apart_from_estimates(ctx: ToolContext) -> None:
    result = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE")
    assert result.data_kind == "modelled_output"
    stress = result.stress_assumptions
    assert stress.scenario.scenario_id == "SHARED_VENDOR_OUTAGE" and stress.scenario.provenance == "predefined_illustrative"
    assert "illustrative" in stress.label and "not calibrated" in stress.label
    assert "not empirically calibrated" in " ".join(stress.scenario.assumption_notes)
    assert stress.stress_parameters.lambda_value == pytest.approx(1.8 * result.baseline_assumptions.lambda_used)
    assert result.baseline_assumptions.lambda_source == "system_history"
    assert result.simulation_results.stress_metrics.p95 > result.simulation_results.baseline_metrics.p95


def test_baseline_in_comparison_equals_the_standalone_baseline_simulation(ctx: ToolContext) -> None:
    baseline = run_loss_simulation(ctx, FOCAL, 20_000, 11)
    compared = compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE", 20_000, 11)
    assert compared.simulation_results.baseline_metrics == baseline.simulation_results.metrics
    assert compared.baseline_assumptions == baseline.model_assumptions
    assert compared.observed_basis == baseline.observed_basis


# ----------------------------------------------------------------- typed errors


@pytest.mark.parametrize("tool", EVERY_TOOL)
def test_unknown_system_gives_a_typed_error(ctx: ToolContext, tool) -> None:
    error = call_any(tool, ctx, "PAYMENT_ENGINE_99")
    assert isinstance(error, ToolError) and error.ok is False
    assert error.error_type == "unknown_system"
    assert "PAYMENT_ENGINE_99" in error.message
    assert "PAYMENT_ENGINE_01" in error.suggestions
    assert error.tool_name == tool.__name__


def test_lowercase_system_id_is_not_accepted_silently_but_is_suggested(ctx: ToolContext) -> None:
    error = get_system_profile(ctx, "payment_engine_01")
    assert error.error_type == "unknown_system" and error.suggestions[0] == "PAYMENT_ENGINE_01"


@pytest.mark.parametrize("bad", [None, 123, "", ["PAYMENT_ENGINE_01"], object()])
@pytest.mark.parametrize("tool", EVERY_TOOL)
def test_invalid_system_id_values_give_typed_errors(ctx: ToolContext, tool, bad: object) -> None:
    error = call_any(tool, ctx, bad)
    assert isinstance(error, ToolError) and error.error_type == "invalid_argument"


def test_sql_injection_attempts_are_treated_as_unknown_ids(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    for attack in ("x'; DROP TABLE incidents; --", "' OR '1'='1", "PAYMENT_ENGINE_01' OR 1=1 --"):
        for tool in EVERY_TOOL:
            assert call_any(tool, ctx, attack).error_type == "unknown_system"
    assert ctx.query("SELECT COUNT(*) AS n FROM incidents")[0]["n"] == len(dataset.incidents)


@pytest.mark.parametrize("months", [0, -1, 121, "12", 12.0, None, True])
@pytest.mark.parametrize("tool", [get_recent_incidents, get_kri_history])
def test_invalid_months_give_typed_errors(ctx: ToolContext, tool, months: object) -> None:
    error = tool(ctx, FOCAL, months=months)
    assert isinstance(error, ToolError) and error.error_type == "invalid_argument" and "months" in error.message


@pytest.mark.parametrize("n, seed", [(0, 1), (999, 1), (1_000_001, 1), ("100", 1), (None, 1), (True, 1),
                                     (10_000, -1), (10_000, "7"), (10_000, 1.5), (10_000, None), (10_000, 2**32)])
def test_invalid_simulation_settings_give_typed_errors(ctx: ToolContext, n: object, seed: object) -> None:
    for error in (run_loss_simulation(ctx, FOCAL, n, seed),
                  compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE", n, seed)):
        assert isinstance(error, ToolError) and error.error_type == "invalid_argument"


def test_unknown_scenario_lists_the_available_ones(ctx: ToolContext) -> None:
    error = compare_baseline_and_stress(ctx, FOCAL, "MADE_UP_SCENARIO")
    assert error.error_type == "unknown_scenario"
    assert error.suggestions == ["SHARED_VENDOR_OUTAGE"] and "SHARED_VENDOR_OUTAGE" in error.message
    assert compare_baseline_and_stress(ctx, FOCAL, None).error_type == "unknown_scenario"


def test_missing_database_is_a_typed_error_and_creates_nothing(tmp_path: Path) -> None:
    missing = ToolContext(db_path=tmp_path / "nope.db")
    for tool in EVERY_TOOL:
        error = call_any(tool, missing, FOCAL)
        assert error.error_type == "data_unavailable" and "python -m risksignal.data.generator" in error.message
    assert not (tmp_path / "nope.db").exists()


def test_engine_value_errors_become_model_errors(ctx: ToolContext) -> None:
    with mock.patch("risksignal.tools.simulation_tools.run_system_simulation",
                    side_effect=ValueError("not enough positive losses")):
        error = run_loss_simulation(ctx, FOCAL)
    assert error.error_type == "model_error" and "not enough positive losses" in error.message


def test_unexpected_exceptions_never_leak(ctx: ToolContext, caplog: pytest.LogCaptureFixture) -> None:
    with mock.patch("risksignal.tools.simulation_tools.run_system_simulation",
                    side_effect=RuntimeError("secret internal detail /home/x.py line 42")):
        error = run_loss_simulation(ctx, FOCAL)
    assert error.error_type == "internal_error"
    assert "secret" not in error.message and "RuntimeError" not in error.message and "Traceback" not in error.message
    assert "secret internal detail" in caplog.text  # logged for developers, not shown to the user


def test_tools_never_raise_for_any_argument_combination(ctx: ToolContext) -> None:
    garbage = [None, 0, -5, 1.5, "", "x" * 10_000, "\x00", object(), [], {}, True]
    for tool in EVERY_TOOL:
        for value in garbage:
            for extra in ([], [value], [value, value], [value, value, value]):
                result = tool(ctx, value, *extra)  # must return, never raise
                assert result.ok is True or isinstance(result, ToolError)
                if isinstance(result, ToolError):
                    assert result.message and "Traceback" not in result.message


# ----------------------------------------------------------------- output shape


def test_all_results_are_json_serialisable_and_round_trip(ctx: ToolContext) -> None:
    for tool in EVERY_TOOL:
        result = call_any(tool, ctx, FOCAL)
        assert result.ok is True and result.tool_name == tool.__name__
        payload = json.loads(result.model_dump_json())
        assert payload["ok"] is True
        assert type(result).model_validate_json(result.model_dump_json()) == result


def test_every_result_says_whether_it_is_observed_or_modelled(ctx: ToolContext) -> None:
    kinds = {tool.__name__: call_any(tool, ctx, FOCAL).data_kind for tool in EVERY_TOOL}
    assert {k for k, v in kinds.items() if v == "modelled_output"} == {"run_loss_simulation", "compare_baseline_and_stress"}
    assert all(v == "observed_synthetic_data" for k, v in kinds.items() if k not in ("run_loss_simulation", "compare_baseline_and_stress"))


def test_data_tools_are_read_only_and_repeatable(ctx: ToolContext, dataset: AtlasBankDataset) -> None:
    first = [call_any(t, ctx, FOCAL) for t in DATA_TOOLS]
    second = [call_any(t, ctx, FOCAL) for t in DATA_TOOLS]
    assert first == second
    assert ctx.query("SELECT COUNT(*) AS n FROM incidents")[0]["n"] == len(dataset.incidents)


def test_tool_functions_keep_their_docstrings_for_the_agent() -> None:
    for tool in EVERY_TOOL:
        assert tool.__doc__ and tool.__name__ == tool.__wrapped__.__name__


# ----------------------------------------------------------------- structural rules


def _import_lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from "))]


def test_tool_modules_do_no_statistics_and_no_direct_database_access() -> None:
    forbidden = ("numpy", "scipy", "sqlite3", "networkx", "anthropic", "risksignal.agent", "risksignal.api",
                 "risksignal.ui", "fastapi", "streamlit")
    for path in TOOLS_DIR.glob("*_tools.py"):
        assert not [i for i in _import_lines(path) if any(f in i for f in forbidden)], path.name


def test_tool_sql_is_read_only_fixed_text_with_bound_parameters_only() -> None:
    sql_verbs = ("SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "PRAGMA", "ATTACH")
    checked = 0
    for path in TOOLS_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.JoinedStr):  # an f-string must never be SQL
                first = node.values[0] if node.values else None
                text = first.value if isinstance(first, ast.Constant) else ""
                assert not text.lstrip().upper().startswith(sql_verbs), f"{path.name}: f-string SQL"
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.lstrip().upper()
                if text.startswith(sql_verbs):
                    checked += 1
                    assert text.startswith("SELECT"), f"{path.name}: non-SELECT statement"
                    assert "{" not in node.value and ";" not in node.value, path.name
    assert checked >= 10  # the scan really found the tools' SQL statements
