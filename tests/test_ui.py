"""Tests for the Streamlit UI. It talks to the real FastAPI app through an in-process test client
and the mock LLM; no server, network or API key is involved."""

import ast
import json
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
    SIMULATION_NOTICE,
    comparison_rows,
    extract_simulation_metadata,
    format_amount,
    format_decimal,
    format_percent,
    label_for,
    split_sections,
)

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
    plain = extract_simulation_metadata(api.investigate("Investigate PAYMENT_ENGINE_01.")["tool_activity"])
    assert plain["tool"] == "run_loss_simulation" and plain["stress_metrics"] is None and plain["random_seed"] == 42
    assert extract_simulation_metadata([]) is None
    assert extract_simulation_metadata([{"tool_name": "get_controls", "status": "completed", "output": {"ok": True}}]) is None


# ----------------------------------------------------------------- charts


def test_kri_figure(api: ApiClient) -> None:
    series = api.kri(FOCAL, 12)["series"][0]
    figure = kri_figure(series)
    assert len(figure.data[0].x) == 12 and list(figure.data[0].y) == [p["value"] for p in series["observations"]]
    assert figure.layout.shapes[0].y0 == series["window_mean"]


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
    assert "not JPMorgan data" in texts(at.markdown)


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
    values = metric_values(at)
    assert {"λ: expected incidents per year", "μ: log-severity location", "σ: log-severity spread"} <= set(values)
    assert float(values["λ: expected incidents per year"]) > 0
    assert any("Parameter interpretation" == e.label for e in at.expander)
    assert at.selectbox[1].value == "SHARED_VENDOR_OUTAGE"
    assert not any("P95 under stress" in label for label in values)

    at.button[0].click().run()
    assert not at.exception
    values = metric_values(at)
    assert {"Mean annual loss under stress", "Median annual loss under stress", "P95 under stress", "P99 under stress",
            "Expected Shortfall 95% under stress", "Expected Shortfall 99% under stress"} <= set(values)
    expected = api.compare(FOCAL, "SHARED_VENDOR_OUTAGE", 100_000, 42)["simulation_results"]
    assert values["P95 under stress"] == format_amount(expected["stress_metrics"]["p95"])
    assert len(at.get("plotly_chart")) == 1
    assert texts(at.info).count(SIMULATION_NOTICE) >= 2  # shown again next to the results
    table = next(d.value for d in at.dataframe if "Baseline" in d.value.columns)
    assert list(table["Metric"])[:3] == ["Mean annual loss", "Median annual loss", "P95"]


def test_scenario_lab_advanced_assumptions_use_the_custom_endpoint(api: ApiClient) -> None:
    at = run_view(api, "scenario_lab", "render_scenario_lab")
    at.checkbox[0].check().run()
    number = {w.label: w for w in at.number_input}
    number["Number of simulations"].set_value(10_000)
    number["λ multiplier"].set_value(2.0)
    number["σ multiplier"].set_value(1.0)
    at.button[0].click().run()
    assert not at.exception
    assert "User-defined scenario" in texts(at.markdown) and "user-supplied" in texts(at.markdown)
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
    assert "P95 under stress" in metric_values(at)
    at.selectbox[0].select("PAYMENT_ENGINE_02").run()
    assert not at.exception and "P95 under stress" not in metric_values(at)


# ----------------------------------------------------------------- page 4: AI investigator


def test_ai_investigator_runs_an_investigation_with_the_mock_llm(api: ApiClient) -> None:
    at = run_view(api, "ai_investigator", "render_ai_investigator")
    assert not at.exception
    assert at.text_area[0].value.startswith("Investigate PAYMENT_ENGINE_01. Review recent incidents, KRIs, controls and dependencies")
    assert "identify questions that an Operational Risk analyst should investigate." in at.text_area[0].value
    assert at.button[0].label == "Investigate this system"

    at.button[0].click().run()
    assert not at.exception
    shown = texts(at.markdown)
    for heading in ("Observed evidence", "Model assumptions", "Simulation results", "Suggested investigation questions"):
        assert f'<span class="rs-title">{heading}</span>' in shown, heading  # each section has its own numbered heading
    assert "Retrieved system profile for PAYMENT_ENGINE_01" in shown
    assert "Ran 100,000 year Monte Carlo simulation (seed 42)" in shown
    assert any("Simulation metadata" in s.value for s in at.subheader)
    assert metric_values(at)["Simulations / seed"] == "100,000 / 42"
    assert "Details: get_system_profile" in [e.label for e in at.expander]
    assert not at.warning[1:] or "numbers" not in texts(at.warning)  # nothing flagged for the honest mock answer


def test_ai_investigator_custom_question_and_stress_option(api: ApiClient) -> None:
    at = run_view(api, "ai_investigator", "render_ai_investigator")
    at.text_area[0].set_value("What controls protect PAYMENT_ENGINE_01?")
    at.checkbox[0].check()
    at.button[0].click().run()
    assert not at.exception and "Request: What controls protect PAYMENT_ENGINE_01? Also compare" in texts(at.caption)
    assert "Compared baseline and stress scenario SHARED_VENDOR_OUTAGE" in texts(at.markdown)


def test_ai_investigator_defaults_follow_the_selected_system(api: ApiClient) -> None:
    at = run_view(api, "ai_investigator", "render_ai_investigator")
    at.selectbox[0].select("PAYMENT_ENGINE_02").run()
    assert at.text_area[0].value.startswith("Investigate PAYMENT_ENGINE_02.")


def test_ai_investigator_explains_a_missing_api_key_without_crashing(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def no_key(question: str):
        raise LLMProviderError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")

    client = make_api(ctx, provider_factory=no_key, provider_name="anthropic")
    at = run_view(client, "ai_investigator", "render_ai_investigator")
    assert not at.exception
    assert "language-model provider is not configured" in texts(at.info) and "ANTHROPIC_API_KEY" in texts(at.info)

    at.button[0].click().run()
    assert not at.exception
    assert "language model is unavailable" in texts(at.error) and "ANTHROPIC_API_KEY" in texts(at.error)
    assert "do not require a language-model API key" in texts(at.info) and "RISKSIGNAL_LLM_PROVIDER=mock" in texts(at.info)
    # the deterministic pages still work with the same backend
    assert not run_view(client, "scenario_lab", "render_scenario_lab").exception
    assert not run_view(client, "system_explorer", "render_system_explorer").exception


def test_ai_investigator_with_an_unknown_system_in_the_request(api: ApiClient) -> None:
    at = run_view(api, "ai_investigator", "render_ai_investigator")
    at.text_area[0].set_value("Investigate PAYMENT_ENGINE_99.")
    at.button[0].click().run()
    assert not at.exception
    assert any(a in texts(at.markdown) for a in ("could not complete the investigation",))
    assert "Failed:" in texts(at.markdown) and "get_system_profile failed (unknown_system)" in texts(at.markdown)


def test_ai_investigator_shows_warnings_for_unmatched_numbers(ctx: ToolContext) -> None:
    from risksignal.agent.base import LLMResponse
    from risksignal.agent.mock_provider import MockProvider

    liar = MockProvider([LLMResponse(text="Simulation results\n- P95 annual loss is 1,234,567.")])
    at = run_view(make_api(ctx, provider_factory=lambda q: liar), "ai_investigator", "render_ai_investigator")
    at.button[0].click().run()
    assert not at.exception and "1,234,567" in texts(at.warning) and "could not be matched" in texts(at.warning)


def test_ai_investigator_without_the_api_does_not_crash() -> None:
    at = run_view(unreachable_api(), "ai_investigator", "render_ai_investigator")
    assert not at.exception and "Cannot reach the RiskSignal API" in texts(at.error)


# ----------------------------------------------------------------- the app entry point


def test_app_entry_point_runs_with_navigation_and_sidebar(api: ApiClient) -> None:
    at = AppTest.from_file(str(SRC / "ui" / "app.py"), default_timeout=60)
    at.session_state["api_client"] = api
    at.run()
    assert not at.exception
    assert at.title[0].value == "Management overview" and BANNER_TEXT in texts(at.warning)
    assert "API ok" in texts(at.sidebar.success) and "Language model: mock (configured)" in texts(at.sidebar.caption)


def test_app_defines_the_pages() -> None:
    source = (SRC / "ui" / "app.py").read_text(encoding="utf-8")
    for title in ("Overview", "Assistant", "System Explorer", "Scenario Analysis", "Investigation"):
        assert f'title="{title}"' in source
    assert "set_page_config" in source


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
        "Research prototype based on synthetic Atlas Bank data; results are not calibrated to observed losses."
    )
    assert SIMULATION_NOTICE == (
        "Simulation results are conditional on the stated assumptions and synthetic data."
    )
    json.dumps([BANNER_TEXT, SIMULATION_NOTICE])
