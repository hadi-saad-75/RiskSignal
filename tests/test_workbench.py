"""Numerical, provenance, API, offline AI and Streamlit workbench acceptance tests."""

import json
import math
import runpy
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from scipy.stats import lognorm, poisson

from risksignal.api.dependencies import Settings, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.agent.tool_registry import build_chat_registry
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.stochastic.diagnostics import evaluate_temporal_model
from risksignal.stochastic.simulation import build_baseline_model
from risksignal.tools.context import ToolContext
from risksignal.tools.monitoring_tools import MAD_SCALE, get_kri_monitoring, monitor_points
from risksignal.tools.schemas import ToolError
from risksignal.tools.validation_tools import get_model_diagnostics
from risksignal.tools.workpaper_tools import evidence_digest, get_risk_workpaper
from risksignal.ui.api_client import ApiClient

FOCAL = "PAYMENT_ENGINE_01"


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("workbench")))


@pytest.fixture
def api(ctx: ToolContext) -> ApiClient:
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(ctx.db_path, "mock")
    return ApiClient(client=TestClient(app))


def points(values: list[float]) -> list[tuple[date, float]]:
    return [(p.date(), value) for p, value in zip(pd.date_range("2025-01-31", periods=len(values), freq="ME"), values)]


def test_monitoring_uses_prior_data_and_exact_threshold() -> None:
    baseline = [1., 2., 1., 2., 1., 2.]
    centre, mad = 1.5, 0.5
    threshold = centre + 3.5 * MAD_SCALE * mad
    at_threshold = monitor_points(points([*baseline, threshold]))[-1]
    above = monitor_points(points([*baseline, threshold + 0.0001]))[-1]
    assert at_threshold.baseline_median == centre
    assert at_threshold.baseline_mad == mad
    assert at_threshold.robust_score == pytest.approx(3.5)
    assert at_threshold.signal == "within_baseline"
    assert above.signal == "unusual_increase"
    assert all(day < above.date for day in above.baseline_dates)


def test_appending_future_values_cannot_change_prior_monitoring() -> None:
    values = points([1., 2.] * 12)
    earlier = monitor_points(values[:-1])
    assert monitor_points([*values[:-1], (values[-1][0], 1e10)])[:-1] == earlier


def test_baseline_uses_at_most_twelve_prior_calendar_months() -> None:
    latest = monitor_points(points([1., 2.] * 14))[-1]
    assert len(latest.baseline_dates) == 12


@pytest.mark.parametrize("value,signal", [
    (3., "within_baseline"), (2., "within_baseline"), (3.01, "flat_baseline_increase"),
])
def test_flat_baseline_never_invents_robust_score(value: float, signal: str) -> None:
    latest = monitor_points(points([3.] * 6 + [value]))[-1]
    assert latest.signal == signal and latest.robust_score is None and latest.baseline_mad == 0


def test_insufficient_and_gapped_history_are_not_scored() -> None:
    assert monitor_points(points([1.] * 6))[-1].signal == "insufficient_history"
    history = points([1.] * 9)
    history.pop(3)
    assert monitor_points(history)[-1].signal == "gapped_history"


@pytest.mark.parametrize("value", [-1., math.nan, math.inf, -math.inf])
def test_nonfinite_or_negative_kri_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        monitor_points(points([value]))


def test_duplicate_calendar_month_rejected() -> None:
    with pytest.raises(ValueError, match="unique calendar months"):
        monitor_points([(date(2026, 1, 1), 1.), (date(2026, 1, 31), 2.)])


def test_monitoring_is_reproducible_and_flag_rate_has_honest_denominator(ctx: ToolContext) -> None:
    result = get_kri_monitoring(ctx, FOCAL)
    assert not isinstance(result, ToolError)
    assert result == get_kri_monitoring(ctx, FOCAL)
    assert len(result.series) == 5
    for series in result.series:
        assert series.data_status == "current" and series.scored_observations == 12
        assert series.flag_rate == pytest.approx(series.flagged_observations / 12)
        assert len(series.history) == len(series.source_refs) == 60


def test_missing_stale_and_future_observations_are_explicit(tmp_path: Path) -> None:
    context = ToolContext(save_atlas_bank(generate_atlas_bank(), tmp_path))
    with sqlite3.connect(context.db_path) as conn:
        conn.execute("DELETE FROM kri_observations WHERE system_id=? AND kri_name='near_miss_count'", (FOCAL,))
        conn.execute("DELETE FROM kri_observations WHERE system_id=? AND date='2026-09-30'", (FOCAL,))
        conn.execute(
            "INSERT INTO kri_observations VALUES ('2026-10-31', ?, 'system_downtime_minutes', 1000000)", (FOCAL,),
        )
    result = get_kri_monitoring(context, FOCAL)
    assert not isinstance(result, ToolError)
    series = {s.kri_name: s for s in result.series}
    assert series["near_miss_count"].data_status == "missing"
    assert series["near_miss_count"].latest is None and series["near_miss_count"].flag_rate is None
    assert series["system_downtime_minutes"].data_status == "stale"
    assert series["system_downtime_minutes"].latest.date == date(2026, 8, 31)


def test_model_diagnostics_reuse_existing_training_only_fit(ctx: ToolContext) -> None:
    result = get_model_diagnostics(ctx, FOCAL)
    assert not isinstance(result, ToolError) and result.status == "evaluated"
    frame = ctx.incidents_frame()
    dates = pd.to_datetime(frame["date"]).dt.date
    training = frame[(dates >= ctx.observation_start) & (dates <= result.training_end_inclusive)]
    reference = build_baseline_model(
        training, FOCAL, observation_start=ctx.observation_start,
        observation_end=result.training_end_inclusive, n_systems=ctx.system_count(),
    )
    assert result.annual_frequency == reference.parameters.lambda_value
    assert result.severity_mu == reference.parameters.mu
    assert result.severity_sigma == reference.parameters.sigma
    assert result.severity_training_losses == reference.severity.n_losses
    assert result.severity_p95 == pytest.approx(lognorm.ppf(
        0.95, s=reference.parameters.sigma, scale=math.exp(reference.parameters.mu),
    ))
    holdout = frame[(dates > result.training_end_inclusive) & (frame["system_id"] == FOCAL)]
    assert result.holdout_incidents == len(holdout)
    assert result.holdout_losses_above_p95 == sum(holdout["financial_loss"] > result.severity_p95)
    assert result.expected_holdout_count == pytest.approx(
        result.annual_frequency * (ctx.as_of_date - result.training_end_inclusive).days / 365.25,
    )
    assert result.count_reference_interval_95 == tuple(
        int(poisson.ppf(p, result.expected_holdout_count)) for p in (0.025, 0.975)
    )


def test_holdout_and_future_mutation_do_not_leak_into_fitted_parameters(ctx: ToolContext) -> None:
    frame = ctx.incidents_frame()
    original = evaluate_temporal_model(frame, FOCAL, ctx.observation_start, ctx.as_of_date, ctx.system_count())
    changed = frame.copy()
    holdout = pd.to_datetime(changed["date"]).dt.date > original.training_end_inclusive
    changed.loc[holdout, "financial_loss"] = 1e12
    after = evaluate_temporal_model(changed, FOCAL, ctx.observation_start, ctx.as_of_date, ctx.system_count())
    assert after.severity_mu == original.severity_mu and after.severity_sigma == original.severity_sigma
    assert after.severity_training_losses == original.severity_training_losses
    assert after.annual_frequency == original.annual_frequency
    assert after.holdout_losses_above_p95 > original.holdout_losses_above_p95
    future = frame.iloc[:1].copy()
    future["date"] = "2027-01-01"
    future["financial_loss"] = 1e12
    assert evaluate_temporal_model(
        pd.concat([frame, future]), FOCAL, ctx.observation_start, ctx.as_of_date, ctx.system_count(),
    ) == original


def test_empty_and_short_history_are_explicitly_not_estimable(ctx: ToolContext) -> None:
    empty = ctx.incidents_frame().iloc[:0]
    result = evaluate_temporal_model(empty, FOCAL, ctx.observation_start, ctx.as_of_date, ctx.system_count())
    assert result.status == "not_estimable" and result.severity_mu is None
    short = evaluate_temporal_model(empty, FOCAL, date(2026, 1, 1), ctx.as_of_date, ctx.system_count())
    assert short.status == "not_estimable" and "No training window" in short.limitations[0]


def test_invalid_losses_are_not_silently_excluded(ctx: ToolContext) -> None:
    frame = ctx.incidents_frame()
    frame.loc[0, "financial_loss"] = math.inf
    with pytest.raises(ValueError, match="finite"):
        evaluate_temporal_model(frame, FOCAL, ctx.observation_start, ctx.as_of_date, ctx.system_count())


def test_workpaper_fingerprint_and_source_references(ctx: ToolContext) -> None:
    result = get_risk_workpaper(ctx, FOCAL)
    assert not isinstance(result, ToolError)
    assert result == get_risk_workpaper(ctx, FOCAL)
    assert result.evidence_sha256 == evidence_digest(result)
    changed = result.model_copy(update={"limitations": ["Changed"]})
    assert evidence_digest(changed) != result.evidence_sha256
    assert result.status == "draft_for_human_review"
    references = {
        *[f"controls:{c.control_id}" for c in result.controls.controls],
        *[f"incidents:{i.incident_id}" for i in result.incidents.incidents],
        *[ref for s in result.monitoring.series for ref in s.source_refs],
        *[f"vendors:{s.vendor.vendor_id}" for s in result.dependencies.shared_vendors],
        f"systems:{FOCAL}", f"processes:{result.profile.primary_process.process_id}",
    }
    assert all(ref in references for q in result.review_questions for ref in q.source_refs)
    assert any(q.topic == "Review follow-up" for q in result.review_questions)
    assert any(q.topic == "Resilience and third parties" for q in result.review_questions)
    assert "effectiveness" in result.limitations[0]


@pytest.mark.parametrize("tool", [get_kri_monitoring, get_model_diagnostics, get_risk_workpaper])
def test_new_tools_preserve_typed_errors(ctx: ToolContext, tmp_path: Path, tool) -> None:
    assert tool(ctx, "UNKNOWN").error_type == "unknown_system"
    assert tool(ToolContext(tmp_path / "absent.db"), FOCAL).error_type == "data_unavailable"
    assert not (tmp_path / "absent.db").exists()


@pytest.mark.parametrize("endpoint", ["monitoring", "model-diagnostics", "workpaper"])
def test_new_api_endpoints_and_client_errors(api: ApiClient, endpoint: str) -> None:
    response = api._request("GET", f"/systems/{FOCAL}/{endpoint}")
    assert response["ok"] and "synthetic" in response["notice"].lower()
    missing = api._http.get(f"/systems/UNKNOWN/{endpoint}")
    assert missing.status_code == 404 and missing.json()["error"]["type"] == "unknown_system"


@pytest.mark.parametrize("message,tool", [
    ("Show KRI alerts for PAYMENT_ENGINE_01", "get_kri_monitoring"),
    ("Show model diagnostics for PAYMENT_ENGINE_01", "get_model_diagnostics"),
    ("Prepare an RCSA workpaper for PAYMENT_ENGINE_01", "get_risk_workpaper"),
])
def test_offline_assistant_uses_real_evidence(api: ApiClient, message: str, tool: str) -> None:
    result = api.chat(message, [], include_tool_outputs=True)
    assert result["status"] == "completed" and result["provider"] == "mock"
    assert [a["tool_name"] for a in result["tool_activity"]] == [tool]
    assert result["tool_activity"][0]["output"]["ok"]
    assert result["ungrounded_numbers"] == []
    assert "synthetic" in result["final_response"].lower()


def workbench(api: ApiClient, review: bool = False, advanced: bool = False) -> AppTest:
    at = AppTest.from_string(
        "from risksignal.ui.views.assistant import render_assistant\nrender_assistant()",
        default_timeout=60,
    )
    at.session_state["api_client"] = api
    at.session_state["evidence_review"] = review
    at.session_state["evidence_advanced"] = advanced
    return at.run()


def test_workbench_renders_all_sections_and_switches_system(api: ApiClient) -> None:
    at = workbench(api)
    assert not at.exception
    assert at.title[0].value == "Risk Investigator"
    snapshot_labels = {
        "Failed deployment rate", "Near miss count", "Control exception count",
        "System downtime minutes", "Vendor incident count",
    }
    assert 1 <= sum(metric.label in snapshot_labels for metric in at.metric) <= 3
    assert {
        "Incidents", "KRI history", "Controls", "Vendors and connected systems",
        "Advanced checks and review questions",
        "Review notes and evidence export",
    }.issubset({e.label for e in at.expander})
    at.selectbox[0].select("CORE_LEDGER_01").run()
    assert not at.exception
    assert at.session_state["workbench_evidence_CORE_LEDGER_01"]["system_id"] == "CORE_LEDGER_01"


@pytest.mark.parametrize("panel", ["profile", "incidents", "kris", "controls", "dependencies"])
def test_evidence_panels_are_lazy_and_remain_available(api: ApiClient, panel: str) -> None:
    at = workbench(api)
    assert not at.exception and not at.dataframe and not at.get("plotly_chart")
    at.session_state[f"evidence_{panel}"] = True
    at.run()
    assert not at.exception
    if panel == "profile":
        assert at.json
    else:
        assert at.dataframe
    if panel == "dependencies":
        at.session_state["evidence_dependencies"] = True
        at.checkbox(key="evidence_dependency_map").check().run()
        assert not at.exception and len(at.get("plotly_chart")) == 1


def test_workpaper_is_reused_until_refresh(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    original = ApiClient.workpaper

    def counted(client: ApiClient, system_id: str) -> dict:
        calls.append(system_id)
        return original(client, system_id)

    monkeypatch.setattr(ApiClient, "workpaper", counted)
    at = workbench(api)
    at.run()
    assert calls == [FOCAL]
    at.button(key="workbench_refresh").click().run()
    assert calls == [FOCAL, FOCAL]


def test_workbench_upgrades_client_retained_across_code_reload(api: ApiClient) -> None:
    client_path = Path(__file__).resolve().parents[1] / "src" / "risksignal" / "ui" / "api_client.py"
    previous_class = runpy.run_path(str(client_path))["ApiClient"]
    for method in ("workpaper", "monitoring", "model_diagnostics"):
        delattr(previous_class, method)
    previous = previous_class(base_url=api.base_url, client=api._http)
    at = workbench(previous)
    assert not at.exception
    upgraded = at.session_state["api_client"]
    assert isinstance(upgraded, ApiClient)
    assert upgraded.base_url == previous.base_url
    assert upgraded._http is previous._http
    assert at.session_state[f"workbench_evidence_{FOCAL}"]["system_id"] == FOCAL
    at.button(key="workbench_refresh").click().run()
    assert not at.exception
    assert at.session_state["api_client"] is upgraded


def test_review_notes_require_input_and_are_bound_to_exported_evidence(api: ApiClient) -> None:
    at = workbench(api, review=True)
    submit = next(b for b in at.button if b.label == "Record review note")
    submit.click().run()
    assert not at.exception and at.error
    evidence = at.session_state[f"workbench_evidence_{FOCAL}"]
    fingerprint = evidence["evidence_sha256"]
    assert at.session_state[f"workbench_reviews_{fingerprint}"] == []
    at.text_input[0].set_value("Risk reviewer")
    at.text_area[1].set_value("Obtain review evidence from the control owner.")
    next(b for b in at.button if b.label == "Record review note").click().run()
    assert not at.exception
    reviews = at.session_state[f"workbench_reviews_{fingerprint}"]
    assert reviews[0]["evidence_sha256"] == fingerprint
    assert reviews[0]["status"] == "note_only_not_signoff"
    download = at.get("download_button")[0]
    assert download.proto.label == "Download evidence and review notes (JSON)"
    assert download.proto.url


def test_workbench_offline_summary_is_labelled_and_uses_matching_evidence(api: ApiClient) -> None:
    at = workbench(api, advanced=True)
    next(b for b in at.button if b.label == "Draft AI evidence summary").click().run()
    assert not at.exception
    assert any("Scripted local draft" in i.value for i in at.info)
    fingerprint = at.session_state[f"workbench_evidence_{FOCAL}"]["evidence_sha256"]
    result = at.session_state[f"workbench_ai_result_{fingerprint}"]
    assert result["tool_activity"][0]["output"]["evidence_sha256"] == fingerprint


def test_workbench_refresh_and_api_unavailability_are_visible(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    at = workbench(api)
    from risksignal.ui.api_client import ApiUnavailableError

    def unavailable(system_id: str) -> dict:
        raise ApiUnavailableError("Test API is offline.")

    monkeypatch.setattr(api, "workpaper", unavailable)
    at.button(key="workbench_refresh").click().run()
    assert not at.exception and at.error
    assert f"workbench_evidence_{FOCAL}" not in at.session_state


def test_download_contains_exact_evidence_and_review_notes(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import streamlit as st

    downloads = []
    original = st.download_button

    def capture(label, data, **kwargs):
        downloads.append(json.loads(data))
        return original(label, data, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)
    at = workbench(api, review=True)
    fingerprint = at.session_state[f"workbench_evidence_{FOCAL}"]["evidence_sha256"]
    at.text_input[0].set_value("Control reviewer")
    at.text_area[1].set_value("Request a test sample and exception log.")
    next(b for b in at.button if b.label == "Record review note").click().run()
    assert not at.exception
    exported = downloads[-1]
    assert exported["evidence"] == api.workpaper(FOCAL)
    assert exported["human_review_notes"] == at.session_state[f"workbench_reviews_{fingerprint}"]
    assert exported["status"] == "draft_not_approved"


@pytest.mark.parametrize("change", ["mismatched_fingerprint", "missing_tool", "incomplete_run"])
def test_ai_draft_requires_completed_matching_source_evidence(
    api: ApiClient, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    response = api.chat(f"Prepare RCSA workpaper for {FOCAL}", [], include_tool_outputs=True)
    if change == "mismatched_fingerprint":
        response["tool_activity"][0]["output"]["evidence_sha256"] = "0" * 64
    elif change == "missing_tool":
        response["tool_activity"] = []
    else:
        response["status"] = "stopped_max_steps"
    monkeypatch.setattr(api, "chat", lambda *args, **kwargs: response)
    at = workbench(api, advanced=True)
    next(b for b in at.button if b.label == "Draft AI evidence summary").click().run()
    assert not at.exception and at.error
    fingerprint = at.session_state[f"workbench_evidence_{FOCAL}"]["evidence_sha256"]
    assert f"workbench_ai_result_{fingerprint}" not in at.session_state


def test_every_system_has_serializable_workbench_evidence(ctx: ToolContext) -> None:
    for row in ctx.query("SELECT system_id FROM systems ORDER BY system_id"):
        result = get_risk_workpaper(ctx, row["system_id"])
        assert not isinstance(result, ToolError)
        assert result.evidence_sha256 == evidence_digest(result)
        json.dumps(result.model_dump(mode="json"), allow_nan=False)


def test_current_but_insufficient_kri_history_is_a_review_question(tmp_path: Path) -> None:
    context = ToolContext(save_atlas_bank(generate_atlas_bank(), tmp_path))
    with sqlite3.connect(context.db_path) as conn:
        conn.execute("DELETE FROM kri_observations WHERE system_id=? AND date<'2026-09-01'", (FOCAL,))
    result = get_risk_workpaper(context, FOCAL)
    assert not isinstance(result, ToolError)
    questions = [q for q in result.review_questions if q.topic == "KRI challenge"]
    assert len(questions) == 5
    assert all("insufficient_history" in q.question for q in questions)


def test_model_view_preserves_sources_and_latest_scores_without_bulk_history(ctx: ToolContext) -> None:
    outcome = build_chat_registry(ctx).run("get_risk_workpaper", {"system_id": FOCAL})
    assert outcome.ok
    for series in outcome.output["monitoring"]["series"]:
        assert "history" not in series
        assert series["latest"] and series["source_refs"]
    assert "history" in get_kri_monitoring(ctx, FOCAL).model_dump()["series"][0]


def test_vendor_kri_not_applicable_is_not_reported_as_missing(ctx: ToolContext) -> None:
    result = get_risk_workpaper(ctx, "CASH_FORECAST_01")
    assert not isinstance(result, ToolError)
    vendor_kri = next(s for s in result.monitoring.series if s.kri_name == "vendor_incident_count")
    assert vendor_kri.data_status == "not_applicable" and vendor_kri.applicability_basis
    assert not any("vendor_incident_count" in q.question for q in result.review_questions)
