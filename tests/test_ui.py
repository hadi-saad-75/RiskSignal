"""Tests for the Streamlit UI. It talks to the real FastAPI app through an in-process test client
and the mock LLM; no server, network or API key is involved."""

import ast
import json
import re
from html import unescape
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from risksignal.agent.base import LLMProviderError
from risksignal.agent.mock_provider import provider_for_question
from risksignal.api.dependencies import Settings, get_provider_factory, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.ui.api_client import ApiClient, ApiRequestError, ApiUnavailableError
from risksignal.ui.charts import (
    dependency_figure,
    dependency_layout,
    distribution_figure,
    kri_figure,
)
from risksignal.ui.formatting import (
    BANNER_TEXT,
    LOSS_UNIT_NOTICE,
    SIMULATION_NOTICE,
    comparison_rows,
    extract_simulation_metadata,
    format_amount,
    format_decimal,
    format_percent,
    label_for,
    split_sections,
    display_prose,
)
from risksignal.text import normalize_prose

FOCAL = "PAYMENT_ENGINE_01"
SRC = Path(__file__).resolve().parents[1] / "src" / "risksignal"


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("ui_db")))


def make_api(ctx: ToolContext, provider_factory=None, provider_name: str = "mock") -> ApiClient:
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=ctx.db_path, llm_provider=provider_name)
    app.dependency_overrides[get_provider_factory] = lambda: (provider_factory or provider_for_question)
    return ApiClient(base_url="http://testserver", client=TestClient(app))


@pytest.fixture(scope="module")
def api(ctx: ToolContext) -> ApiClient:
    return make_api(ctx)


def unreachable_api() -> ApiClient:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    return ApiClient(base_url="http://127.0.0.1:1", client=httpx.Client(base_url="http://127.0.0.1:1", transport=httpx.MockTransport(refuse)))


def run_view(client: ApiClient, module: str, function: str) -> AppTest:
    at = AppTest.from_string(f"from risksignal.ui.views.{module} import {function}\n{function}()", default_timeout=60)
    at.session_state["api_client"] = client
    return at.run()


def texts(elements: Any) -> str:
    return " | ".join(str(e.value) for e in elements)


def metric_values(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


# ----------------------------------------------------------------- pure helpers


def test_number_formatting() -> None:
    assert format_amount(896435.3) == "896,435" and format_amount(None) == "n/a"
    assert format_decimal(3.8005, 2) == "3.80" and format_decimal(None) == "n/a"
    assert format_percent(154.14) == "+154.1%" and format_percent(-3.2) == "-3.2%" and format_percent(None) == "n/a"
    assert label_for("failed_deployment_rate") == "Failed deployment rate"


def test_display_punctuation_preserves_raw_evidence_and_values() -> None:
    raw = {"description": "Failure\u2014release rolled back; review needed.", "financial_loss": 1234.5,
           "tool_input": {"system_id": "PAYMENT_ENGINE_01"}, "flags": [True, None]}
    clean = display_prose(raw)
    assert clean["description"] == "Failure, release rolled back, review needed."
    assert clean["financial_loss"] == raw["financial_loss"]
    assert clean["tool_input"] == raw["tool_input"] and clean["flags"] == raw["flags"]
    assert ";" in raw["description"] and "\u2014" in raw["description"]
    assert normalize_prose("2021\u20132026; frequency\u2013severity") == "2021 to 2026, frequency-severity"


@pytest.mark.parametrize("text", [
    "Observed evidence\n- a\n\nSimulation results\n- b",
    "## Observed evidence\n- a\n\n## Simulation results\n- b",
    "**Observed evidence**\n- a\n\n**Simulation results:**\n- b",
    "1. Observed evidence:\n- a\n\n2. Simulation Results\n- b",
    "OBSERVED EVIDENCE\n- a\nsimulation results\n- b",
])
def test_split_sections_understands_common_heading_styles(text: str) -> None:
    assert split_sections(text) == [("Observed evidence", "- a"), ("Simulation results", "- b")]


def test_split_sections_edge_cases() -> None:
    assert split_sections("Just a plain answer.") == [("Answer", "Just a plain answer.")]
    assert split_sections("   ") == []
    parts = split_sections("Intro line.\n\nModel assumptions\n- x\nSuggested investigation questions\n- q?")
    assert parts == [("Summary", "Intro line."), ("Model assumptions", "- x"), ("Suggested investigation questions", "- q?")]
    # a heading word inside a sentence is not a heading
    assert split_sections("The Limitations of this model are many.") == [("Answer", "The Limitations of this model are many.")]


def test_comparison_rows_use_the_api_numbers(api: ApiClient) -> None:
    result = api.compare(FOCAL, "SHARED_VENDOR_OUTAGE", 5_000, 1)
    rows = comparison_rows(result["simulation_results"])
    assert [r["Metric"] for r in rows][:3] == ["Mean annual loss", "Median annual loss", "P95"]
    p95 = rows[2]
    assert p95["Baseline"] == format_amount(result["simulation_results"]["baseline_metrics"]["p95"])
    assert p95["Change"] == format_percent(result["simulation_results"]["percentage_differences"]["p95"])


def test_simulation_metadata_is_extracted_from_the_tool_output(api: ApiClient) -> None:
    response = api.investigate("Investigate PAYMENT_ENGINE_01 with the stress scenario.")
    meta = extract_simulation_metadata(response["tool_activity"])
    assert meta["tool"] == "compare_baseline_and_stress" and meta["stress_metrics"]["p95"] > meta["baseline_metrics"]["p95"]
    plain = extract_simulation_metadata(api.investigate("Investigate PAYMENT_ENGINE_01 and simulate annual losses.")["tool_activity"])
    assert plain["tool"] == "run_loss_simulation" and plain["stress_metrics"] is None and plain["random_seed"] == 42
    assert extract_simulation_metadata([]) is None
    assert extract_simulation_metadata([{"tool_name": "get_controls", "status": "completed", "output": {"ok": True}}]) is None


# ----------------------------------------------------------------- charts


def test_kri_figure(api: ApiClient) -> None:
    series = api.kri(FOCAL, 12)["series"][0]
    figure = kri_figure(series)
    assert len(figure.data[0].x) == 12 and list(figure.data[0].y) == [p["value"] for p in series["observations"]]
    assert figure.layout.shapes[0].y0 == series["window_mean"]
    assert figure.layout.xaxis.title.text == "Month"
    assert figure.layout.yaxis.title.text == "Count"
    for name, unit in (("failed_deployment_rate", "% of deployments"), ("system_downtime_minutes", "Minutes")):
        selected = next(s for s in api.kri(FOCAL, 12)["series"] if s["kri_name"] == name)
        assert kri_figure(selected).layout.yaxis.title.text == unit


def test_distribution_figure_draws_a_proper_density(api: ApiClient) -> None:
    out = api.compare(FOCAL, "SHARED_VENDOR_OUTAGE", 20_000, 1)["simulation_results"]
    figure = distribution_figure(out["baseline_histogram"], out["baseline_metrics"]["p95"],
                                 out["stress_histogram"], out["stress_metrics"]["p95"])
    assert [t.name for t in figure.data] == ["Baseline", "Stress"] and len(figure.layout.shapes) == 2
    for trace, key in zip(figure.data, ("baseline_histogram", "stress_histogram")):
        edges = list(trace.x)
        area = sum(trace.y[i] * (edges[i + 1] - edges[i]) for i in range(len(edges) - 1))
        assert area == pytest.approx(0.99, abs=0.005)  # the plotted range covers 99% of simulated years
    only_baseline = distribution_figure(out["baseline_histogram"], out["baseline_metrics"]["p95"])
    assert [t.name for t in only_baseline.data] == ["Baseline"]


def test_dependency_layout_shows_the_shared_vendor_path(api: ApiClient) -> None:
    layout = dependency_layout(FOCAL, api.dependencies(FOCAL))
    nodes = {n["key"]: n for n in layout["nodes"]}
    assert len(nodes) == len(layout["nodes"])  # unique node keys
    assert nodes[f"system:{FOCAL}"]["kind"] == "focus" and (nodes[f"system:{FOCAL}"]["x"], nodes[f"system:{FOCAL}"]["y"]) == (0.0, 0.0)
    assert {"vendor:V02", "vendor:V04", "process:P01", "related:PAYMENT_ENGINE_02"} <= set(nodes)
    edges = {(e["source"], e["target"]) for e in layout["edges"]}
    assert (f"system:{FOCAL}", "vendor:V04") in edges and ("vendor:V04", "related:PAYMENT_ENGINE_02") in edges
    assert all(e["source"] in nodes and e["target"] in nodes for e in layout["edges"])
    assert "Keystone Payment Rails" in nodes["related:PAYMENT_ENGINE_02"]["hover"]
    assert {n["x"] for n in layout["nodes"]} == {0.0, 1.0, 2.0}


def test_dependency_figure_renders_and_handles_isolated_systems(api: ApiClient) -> None:
    figure = dependency_figure(FOCAL, api.dependencies(FOCAL))
    assert {t.name for t in figure.data if t.name} == {"Selected system", "Vendor", "Business process", "Related system"}
    empty = {"vendors": [], "supported_processes": [], "related_systems": []}
    alone = dependency_figure("LONELY_01", empty)
    assert [t.name for t in alone.data] == ["Selected system"]


# ----------------------------------------------------------------- API client


def test_client_returns_api_data(api: ApiClient) -> None:
    assert api.health()["status"] == "ok" and api.systems()["systems"][0]["system_id"]
    assert api.profile(FOCAL)["system"]["system_id"] == FOCAL and api.controls(FOCAL)["controls"]
    assert api.scenarios()["scenarios"][0]["scenario_id"] == "SHARED_VENDOR_OUTAGE"
    assert api.overview(3)["recent_incidents"].__len__() == 3
    assert api.simulate(FOCAL, 2_000, 5)["model_assumptions"]["random_seed"] == 5
    custom = api.compare_custom(FOCAL, 2.0, 1.0, 2_000, 5)
    assert custom["stress_assumptions"]["scenario"]["provenance"] == "user_supplied"


def test_client_turns_api_errors_into_typed_exceptions(api: ApiClient) -> None:
    with pytest.raises(ApiRequestError) as unknown:
        api.profile("PAYMENT_ENGINE_99")
    assert unknown.value.status_code == 404 and unknown.value.error_type == "unknown_system"
    assert "PAYMENT_ENGINE_01" in unknown.value.suggestions
    with pytest.raises(ApiRequestError) as invalid:
        api.simulate(FOCAL, 10, 1)
    assert invalid.value.status_code == 422 and invalid.value.error_type == "validation_error"


def test_client_reports_an_unreachable_api() -> None:
    with pytest.raises(ApiUnavailableError, match="Cannot reach"):
        unreachable_api().health()

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = ApiClient(base_url="http://x", client=httpx.Client(base_url="http://x", transport=httpx.MockTransport(slow)))
    with pytest.raises(ApiUnavailableError, match="in time"):
        client.health()


def test_client_survives_non_json_error_bodies() -> None:
    client = ApiClient(base_url="http://x", client=httpx.Client(base_url="http://x", transport=httpx.MockTransport(
        lambda request: httpx.Response(502, text="<html>Bad gateway</html>"))))
    with pytest.raises(ApiRequestError) as error:
        client.health()
    assert error.value.status_code == 502 and "502" in error.value.message


def test_client_base_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISKSIGNAL_API_URL", "http://example.invalid:9999/")
    assert ApiClient().base_url == "http://example.invalid:9999"
    assert ApiClient(base_url="http://other").base_url == "http://other"


# ----------------------------------------------------------------- page 1: overview


def test_overview_page(api: ApiClient) -> None:
    at = run_view(api, "overview", "render_overview")
    assert not at.exception
    assert BANNER_TEXT in texts(at.warning)
    assert at.title[0].value == "Management overview"
    metrics = metric_values(at)
    assert set(metrics) == {"Incident records", "Recorded loss", "Overdue controls", "Systems in scope"}
    assert metrics["Incident records"] != "0"
    assert metrics["Recorded loss"] != "0"
    assert metrics["Systems in scope"] == "20"
    assert any("Latest incidents" in s.value for s in at.subheader)
    frame = at.dataframe[0].value
    assert len(frame) == 5 and {"Date", "System", "Category", "Severity", "Loss"} == set(frame.columns)
    assert "risk score" not in (texts(at.markdown) + texts(at.subheader) + texts(at.caption)).lower()
    assert "fictional Atlas Bank data" in texts(at.markdown)
    assert "JPMorgan" not in texts(at.markdown)
    assert LOSS_UNIT_NOTICE in texts(at.caption)


def test_overview_without_the_api_shows_help_and_does_not_crash() -> None:
    at = run_view(unreachable_api(), "overview", "render_overview")
    assert not at.exception
    assert "Cannot reach the RiskSignal API" in texts(at.error) and "uvicorn risksignal.api.main:app" in texts(at.error)


# ----------------------------------------------------------------- page 2: system explorer


def test_system_explorer_page(api: ApiClient) -> None:
    at = run_view(api, "system_explorer", "render_system_explorer")
    assert not at.exception and BANNER_TEXT in texts(at.warning)
    assert at.selectbox[0].value == FOCAL
    assert [t.label for t in at.tabs] == ["Profile", "Incidents", "KRIs", "Controls", "Dependencies and related systems"]
    values = metric_values(at)
    assert values["Criticality"] == "Critical" and values["Controls"] == "4" and values["KRIs tracked"] == "5"
    assert int(values["Descriptions mentioning deployment"]) >= 2
    assert len(at.get("plotly_chart")) == 6  # five KRIs and the shared exposure map
    tables = [d.value for d in at.dataframe]
    assert any("Also used by" in t.columns and t["Also used by"].str.contains("PAYMENT_ENGINE_02").any() for t in tables)
    assert any("Relationship" in t.columns and t["Relationship"].str.contains("Keystone Payment Rails").any() for t in tables)
    assert any("Status" in t.columns and t["Status"].str.contains("Overdue").any() for t in tables)
    assert LOSS_UNIT_NOTICE in texts(at.caption)
    descriptions = next(t["Description"] for t in tables if "Incident" in t.columns)
    assert not descriptions.str.contains("[;\u2013\u2014]").any()


def test_system_explorer_switches_system_and_window(api: ApiClient) -> None:
    at = run_view(api, "system_explorer", "render_system_explorer")
    at.selectbox[0].select("PAYMENT_ENGINE_02").run()
    assert not at.exception and "Payment Engine 02" in texts(at.subheader)
    at.slider[0].set_value(24).run()
    assert not at.exception
    assert at.session_state["selected_system"] == "PAYMENT_ENGINE_02"


# ----------------------------------------------------------------- page 3: scenario lab


def test_scenario_lab_shows_estimates_notice_and_runs_baseline_and_stress(api: ApiClient) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    assert not at.exception
    assert SIMULATION_NOTICE in texts(at.info)
    assert not at.metric
    assert any("Advanced assumptions" == e.label for e in at.expander)
    assert LOSS_UNIT_NOTICE in texts(at.caption)
    assert "ILLUSTRATIVE ONLY" in texts(at.markdown)
    assert "exp(0.2) = 1.221" in texts(at.markdown)
    assert at.selectbox[1].value == "SHARED_VENDOR_OUTAGE"
    assert not any("P95 under stress" in label for label in metric_values(at))

    at.button[0].click().run()
    assert not at.exception
    assumptions = texts(at.markdown)
    assert "Controls, KRIs and dependencies between systems do not enter the model" in assumptions
    assert "No causal link between a vendor event" in assumptions
    assert "bell-shaped with mean" not in assumptions
    assert "Created by Hadi Saad" in texts(at.caption)
    values = metric_values(at)
    assert {"λ: expected incidents per year", "μ: log-severity location", "σ: log-severity spread"} <= set(values)
    expected = api.compare(FOCAL, "SHARED_VENDOR_OUTAGE", 100_000, 42)["simulation_results"]
    headline = at.dataframe[0].value
    assert headline.loc[headline["Metric"] == "P95", "Stress"].iloc[0] == format_amount(expected["stress_metrics"]["p95"])
    assert not at.get("plotly_chart")
    at.session_state["lab_distribution"] = True
    at.run()
    assert len(at.get("plotly_chart")) == 1
    table = next(d.value for d in at.dataframe if "Baseline" in d.value.columns)
    assert list(table["Metric"]) == ["Mean annual loss", "P95", "Expected Shortfall 95%"]


def test_scenario_lab_advanced_assumptions_use_the_custom_endpoint(api: ApiClient) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    at.checkbox[0].check().run()
    number = {w.label: w for w in at.number_input}
    number["Number of simulations"].set_value(10_000)
    number["λ multiplier"].set_value(2.0)
    number["σ multiplier"].set_value(1.0)
    at.button[0].click().run()
    assert not at.exception
    assert "user-supplied" in texts(at.caption).lower()
    parameters = next(t.value for t in at.table if "Parameter" in t.value.columns and "Stress" in t.value.columns)
    baseline_lambda = float(parameters["Baseline"].iloc[0])
    assert float(parameters["Stress"].iloc[0]) == pytest.approx(2 * baseline_lambda, rel=0.01)
    assert parameters["Stress"].iloc[2] == parameters["Baseline"].iloc[2]  # sigma multiplier of 1


def test_scenario_lab_inputs_are_limited_and_disabled_until_chosen(api: ApiClient) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    number = {w.label: w for w in at.number_input}
    assert number["λ multiplier"].disabled and number["σ multiplier"].disabled
    assert number["Number of simulations"].min == 1_000 and number["Number of simulations"].max == 1_000_000
    assert number["Random seed"].min == 0


def test_scenario_lab_new_system_clears_stale_results(api: ApiClient) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    at.button[0].click().run()
    assert at.dataframe
    at.selectbox[0].select("PAYMENT_ENGINE_02").run()
    assert not at.exception and not at.dataframe


# ----------------------------------------------------------------- Assistant page: investigation section


def test_investigation_runs_an_investigation_with_the_mock_llm(api: ApiClient) -> None:
    at = run_view(api, "assistant", "render_assistant")
    assert not at.exception
    assert at.text_area[0].value.startswith("Investigate PAYMENT_ENGINE_01. Review current monitoring signals")
    assert "suggest next steps." in at.text_area[0].value
    snapshot_labels = {
        "Failed deployment rate", "Near miss count", "Control exception count",
        "System downtime minutes", "Vendor incident count",
    }
    assert 1 <= sum(metric.label in snapshot_labels for metric in at.metric) <= 3
    assert at.button(key="agent_investigate").label == "Investigate system"

    at.button(key="agent_investigate").click().run()
    assert not at.exception
    assert "Operational monitoring context for PAYMENT_ENGINE_01" in at.session_state["agent_response"]["question"]
    shown = texts(at.markdown)
    for heading in ("Investigation Summary", "Key Findings", "Next Investigations"):
        assert heading in texts(at.subheader)
    assert "Simulation results" not in [e.label for e in at.expander]
    at.session_state["evidence_tools"] = True
    at.run()
    shown = texts(at.markdown)
    assert "Retrieved system profile for PAYMENT_ENGINE_01" in shown
    assert "Ran 100,000 year Monte Carlo simulation (seed 42)" not in shown
    assert any("system_id" in element.value for element in at.json)
    expander_labels = [e.label for e in at.expander]
    assert expander_labels.index("Retrieved evidence and tool activity") < expander_labels.index(
        "Review notes and evidence export"
    )
    assert "Scripted offline" in texts(at.caption)
    assert not at.warning[1:] or "numbers" not in texts(at.warning)


def test_investigation_blank_request_clears_previous_answer(api: ApiClient) -> None:
    at = run_view(api, "assistant", "render_assistant")
    at.button(key="agent_investigate").click().run()
    assert at.session_state["agent_response"]
    at.text_area(key=f"agent_question_{FOCAL}").set_value("  ").run()
    at.button(key="agent_investigate").click().run()
    assert "Enter an investigation question" in texts(at.error)
    assert "Investigation Summary" not in texts(at.subheader)


def test_failed_investigation_does_not_show_old_findings(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    at = run_view(api, "assistant", "render_assistant")
    at.button(key="agent_investigate").click().run()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise ApiRequestError(503, "llm_unavailable", "Provider unavailable for this check.")

    monkeypatch.setattr(ApiClient, "investigate", fail)
    at.button(key="agent_investigate").click().run()
    assert not at.exception
    assert "Provider unavailable" in texts(at.error)
    assert "Investigation Summary" not in texts(at.subheader)


def test_main_views_do_not_run_simulations_on_open(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Opening a view must not run a simulation.")

    monkeypatch.setattr(ApiClient, "simulate", unexpected)
    for module, function in (("assistant", "render_assistant"), ("scenario_lab", "render_scenario_lab")):
        at = run_view(api, module, function)
        assert not at.exception and not at.get("plotly_chart")


def test_scenario_changed_inputs_warn_and_failed_rerun_clears_results(
    api: ApiClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    at.button[0].click().run()
    next(n for n in at.number_input if n.label == "Random seed").set_value(43).run()
    assert "Settings have changed" in texts(at.warning)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise ApiRequestError(400, "invalid_input", "Simulation rejected for this check.")

    monkeypatch.setattr(ApiClient, "compare", fail)
    at.button[0].click().run()
    assert not at.exception and not at.dataframe
    assert "Simulation rejected" in texts(at.error)


def test_numbered_agent_items_are_capped_without_losing_full_response(api: ApiClient) -> None:
    from risksignal.ui.views.investigation import _bullets

    assert _bullets("1. First\n   source\n2) Second\n3. Third\n4. Fourth") == [
        "- First\n   source", "- Second", "- Third", "- Fourth",
    ]
    response = api.investigate(f"Investigate {FOCAL}.")
    response["final_response"] = (
        "Investigation Summary\nOne sentence. Two sentences. Three sentences. Fourth sentence.\n"
        "Key Findings\n1. First\n2. Second\n3. Third\n4. Hidden finding\n"
        "Next Investigations\n1. Review first\n2. Review second\n3. Review third\n4. Hidden priority"
    )
    at = AppTest.from_string(
        "import streamlit as st\nfrom risksignal.ui.views.investigation import _show\n"
        "_show(st.session_state['response'], 'Test response')"
    )
    at.session_state["response"] = response
    at.run()
    assert not at.exception
    # The complete response is retained only in disclosure, not discarded.
    main = " | ".join(e.value for e in at.markdown if "Hidden finding" not in e.value)
    assert "Fourth sentence" not in main
    assert sum("**" in e.value for e in at.markdown) == 3
    assert "Hidden priority" in texts(at.expander[0].markdown)


def test_malformed_agent_output_is_reported_and_preserved_in_disclosure(api: ApiClient) -> None:
    response = api.investigate(f"Investigate {FOCAL}.")
    response["final_response"] = "Unstructured answer\n" + "\n".join(f"- Finding {i}" for i in range(10))
    at = AppTest.from_string(
        "import streamlit as st\nfrom risksignal.ui.views.investigation import _show\n"
        "_show(st.session_state['response'], 'Test response')"
    )
    at.session_state["response"] = response
    at.run()
    assert not at.exception
    assert "did not return the expected investigation sections" in texts(at.warning)
    assert not at.subheader
    assert "Finding 9" in texts(at.expander[0].markdown)


def test_investigation_custom_question_and_stress_option(api: ApiClient) -> None:
    at = run_view(api, "assistant", "render_assistant")
    at.text_area[0].set_value("What controls protect PAYMENT_ENGINE_01?")
    at.checkbox[0].check()
    at.button(key="agent_investigate").click().run()
    assert not at.exception and "Request: What controls protect PAYMENT_ENGINE_01?" in texts(at.caption)
    at.session_state["evidence_tools"] = True
    at.run()
    assert "Compared baseline and stress scenario SHARED_VENDOR_OUTAGE" in texts(at.markdown)


def test_investigation_defaults_follow_the_selected_system(api: ApiClient) -> None:
    at = run_view(api, "assistant", "render_assistant")
    at.selectbox[0].select("PAYMENT_ENGINE_02").run()
    assert at.text_area[0].value.startswith("Investigate PAYMENT_ENGINE_02.")


def test_investigation_explains_a_missing_api_key_without_crashing(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def no_key(question: str):
        raise LLMProviderError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")

    client = make_api(ctx, provider_factory=no_key, provider_name="anthropic")
    at = run_view(client, "assistant", "render_assistant")
    assert not at.exception
    assert "language-model provider is not configured" in texts(at.info) and "ANTHROPIC_API_KEY" in texts(at.info)

    at.button(key="agent_investigate").click().run()
    assert not at.exception
    assert "language model is unavailable" in texts(at.error) and "ANTHROPIC_API_KEY" in texts(at.error)
    assert "do not require a language-model API key" in texts(at.info) and "RISKSIGNAL_LLM_PROVIDER=mock" in texts(at.info)
    # the deterministic pages still work with the same backend
    assert not run_view(client, "scenario_lab", "render_scenario_lab").exception
    assert not run_view(client, "system_explorer", "render_system_explorer").exception


def test_investigation_with_an_unknown_system_in_the_request(api: ApiClient) -> None:
    at = run_view(api, "assistant", "render_assistant")
    at.text_area[0].set_value("Investigate PAYMENT_ENGINE_99.")
    at.button(key="agent_investigate").click().run()
    assert not at.exception
    assert any(a in texts(at.markdown) for a in ("could not complete the investigation",))
    assert "get_system_profile failed (unknown_system)" in texts(at.error)


def test_investigation_shows_warnings_for_unmatched_numbers(ctx: ToolContext) -> None:
    from risksignal.agent.base import LLMResponse
    from risksignal.agent.mock_provider import MockProvider

    liar = MockProvider([LLMResponse(text="Simulation results\n- P95 annual loss is 1,234,567.")])
    at = run_view(make_api(ctx, provider_factory=lambda q: liar), "assistant", "render_assistant")
    at.button(key="agent_investigate").click().run()
    assert not at.exception and "1,234,567" in texts(at.warning) and "could not be matched" in texts(at.warning)


def test_investigation_without_the_api_does_not_crash() -> None:
    at = run_view(unreachable_api(), "assistant", "render_assistant")
    assert not at.exception and "Cannot reach the RiskSignal API" in texts(at.error)


# ----------------------------------------------------------------- the app entry point


def test_app_entry_point_runs_with_navigation_and_sidebar(api: ApiClient) -> None:
    at = AppTest.from_file(str(SRC / "ui" / "app.py"), default_timeout=60)
    at.session_state["api_client"] = api
    at.run()
    assert not at.exception
    assert at.title[0].value == "Risk Investigator"
    assert not at.get("page_link")
    assert "API ok" in texts(at.sidebar.success) and "Language model: mock (configured)" in texts(at.sidebar.caption)
    content = texts(at.markdown) + texts(at.caption) + texts(at.info) + texts(at.subheader)
    for phrase in (
        "AI Operational Risk Investigator", "System context", "Supporting Evidence",
    ):
        assert phrase in content
    assert not at.get("plotly_chart")
    assert not any(phrase in content for phrase in (
        "How Atlas Bank was built", "How RiskSignal was engineered",
        "SQLite", "NetworkX", "FastAPI",
    ))
    assert not any(phrase in content for phrase in (
        "Read at your own pace", "Present from left to right", "Evidence supports judgement",
    ))


def test_intro_remains_readable_without_the_backend() -> None:
    at = AppTest.from_file(str(SRC / "ui" / "app.py"), default_timeout=60)
    at.session_state["api_client"] = unreachable_api()
    at.run()
    assert not at.exception and at.title[0].value == "Risk Investigator"
    assert "API unavailable" in texts(at.sidebar.error)
    assert "Cannot reach the RiskSignal API" in texts(at.error)
    assert not at.get("page_link")


def test_way_forward_covers_slide_topics_and_labels_unbuilt_work(api: ApiClient) -> None:
    at = run_view(api, "way_forward", "render_way_forward")
    assert not at.exception and at.title[0].value == "Way Forward"
    content = texts(at.markdown) + texts(at.subheader)
    for phrase in (
        "Agree one real task", "approved real bank data", "regulations and internal rules",
        "Fit and test a real-data loss model", "Test the live LLM",
        "kept out of fitting", "source correctness", "review time", "independent review",
    ):
        assert phrase in content
    assert "multi-agent" not in content.lower()
    assert "Basel standardised" not in content
    assert "Conversational preview" not in content
    assert "What success would look like" not in content
    assert "Offline mock provider" not in texts(at.info)
    assert "Created by Hadi Saad" in texts(at.caption)
    assert "there is no live LLM" in texts(at.caption)
    assert not at.chat_input
    assert not at.button


@pytest.mark.parametrize("module, function", [
    ("overview", "render_overview"),
    ("system_explorer", "render_system_explorer"),
    ("scenario_lab", "render_scenario_lab"),
    ("assistant", "render_assistant"),
    ("way_forward", "render_way_forward"),
])
def test_visible_prose_avoids_long_dashes_and_semicolons(api: ApiClient, module: str, function: str) -> None:
    at = run_view(api, module, function)
    if module == "assistant":
        at.button(key="agent_investigate").click().run()
    elif module == "scenario_lab":
        at.button[0].click().run()
    assert not at.exception
    visible = " ".join(
        texts(getattr(at, kind)) for kind in ("markdown", "caption", "warning", "info", "error", "subheader")
    )
    for table in at.dataframe:
        visible += table.value.to_string()
    for element in at.get("json"):
        visible += str(element.value)
    visible = unescape(re.sub(r"<[^>]*>", "", visible))
    assert not any(character in visible for character in (";", "\u2013", "\u2014"))


def test_app_defines_the_pages() -> None:
    source = (SRC / "ui" / "app.py").read_text(encoding="utf-8")
    titles = ("Overview", "Risk Investigator", "Scenario Analysis", "Way Forward")
    for title in titles:
        assert f'title="{title}"' in source
    assert "set_page_config" in source
    positions = [source.index(f'title="{title}"') for title in titles]
    assert positions == sorted(positions)
    assert "default=True" in source
    assert source.count("st.Page(") == 4
    assert 'title="Database"' not in source
    assert "render_risk_workbench" not in source
    assert "Risk workbench" not in source
    assert 'url_path="introduction"' in source


def test_introduction_explains_approach_need_goal_and_idea_without_api() -> None:
    at = AppTest.from_string(
        "from risksignal.ui.views.product_context import render_introduction\nrender_introduction()"
    ).run()
    assert not at.exception
    assert at.title[0].value == "Overview" and not at.expander
    assert [heading.value for heading in at.subheader] == ["Current approach", "The need", "The goal", "The idea"]
    assert "LLM" in texts(at.markdown)
    assert "The data are synthetic Atlas Bank records" in texts(at.caption)
    assert "offline mock follows a script" in texts(at.caption)
    assert "Created by Hadi Saad" in texts(at.caption)
    assert "help analysts decide what to investigate next" in texts(at.markdown)
    assert "three" not in texts(at.markdown)


def test_database_is_scrollable_with_table_selection_and_pages(
    api: ApiClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    original = ApiClient.database

    def counted(client: ApiClient, table: str, offset: int = 0, limit: int = 100) -> dict:
        calls.append((table, offset, limit))
        return original(client, table, offset, limit)

    monkeypatch.setattr(ApiClient, "database", counted)
    at = AppTest.from_string(
        "import streamlit as st\nfrom risksignal.ui.views.product_context import render_database\n"
        "render_database(st.session_state['api_client'])"
    )
    at.session_state["api_client"] = api
    at.run()
    assert not at.exception and len(at.dataframe[0].value) == 20
    assert calls == [("systems", 0, 100)] and not at.expander
    assert list(at.dataframe[0].value.columns) == api.database("systems")["columns"]
    at.selectbox(key="database_table").select("kri_observations").run()
    first = at.dataframe[0].value.to_dict("records")
    assert len(first) == 100
    at.number_input(key="database_page_kri_observations").set_value(2).run()
    assert at.dataframe[0].value.to_dict("records") == api.database("kri_observations", 100)["rows"]
    assert "Showing 101-200" in texts(at.caption)
    at.number_input(key="database_page_kri_observations").set_value(10000).run()
    assert not at.exception and not at.dataframe and "No records on this page" in texts(at.info)


def test_database_api_failure_is_explicit(api: ApiClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise ApiRequestError(503, "data_unavailable", "Database unavailable for this check.")

    monkeypatch.setattr(ApiClient, "database", fail)
    at = AppTest.from_string(
        "import streamlit as st\nfrom risksignal.ui.views.product_context import render_database\n"
        "render_database(st.session_state['api_client'])"
    )
    at.session_state["api_client"] = api
    at.run()
    assert not at.exception and "Database unavailable" in texts(at.error) and not at.dataframe


# ----------------------------------------------------------------- structure


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def test_ui_talks_only_to_the_api_and_imports_no_engines() -> None:
    forbidden = ("risksignal.stochastic", "risksignal.graph", "risksignal.agent", "risksignal.tools",
                 "risksignal.data", "risksignal.api", "numpy", "scipy", "networkx", "sqlite3", "anthropic", "fastapi")
    paths = list((SRC / "ui").rglob("*.py"))
    assert len(paths) >= 9
    for path in paths:
        found = [n for n in _imports(path) if any(n == f or n.startswith(f + ".") for f in forbidden)]
        assert not found, f"{path.name}: {found}"


def test_lower_layers_do_not_import_the_ui() -> None:
    for package in ("data", "stochastic", "graph", "tools", "agent", "api"):
        for path in (SRC / package).glob("*.py"):
            assert not [n for n in _imports(path) if n.startswith("risksignal.ui")], path.name


def test_the_banner_and_notice_texts_are_exact() -> None:
    assert BANNER_TEXT == (
        "Research prototype based on synthetic Atlas Bank data, results are not calibrated to observed losses."
    )
    assert SIMULATION_NOTICE == (
        "Simulation results are conditional on the stated assumptions and synthetic data."
    )
    json.dumps([BANNER_TEXT, SIMULATION_NOTICE])
