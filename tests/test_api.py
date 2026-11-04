"""Tests for the FastAPI backend. The agent endpoint uses the mock LLM only; nothing calls a paid API."""

import ast
import json
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from risksignal import __version__
from risksignal.agent.base import LLMProviderError, LLMResponse
from risksignal.agent.mock_provider import MockProvider, provider_for_question
from risksignal.api import dependencies, routes_agent, routes_simulation, routes_systems
from risksignal.api.dependencies import Settings, get_provider_factory, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.tools.simulation_tools import compare_baseline_and_stress, run_loss_simulation

FOCAL = "PAYMENT_ENGINE_01"
SRC = Path(__file__).resolve().parents[1] / "src" / "risksignal"


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("api_db")))


def make_client(ctx: ToolContext, provider_factory=None, provider_name: str = "mock", **kwargs) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=ctx.db_path, llm_provider=provider_name)
    app.dependency_overrides[get_provider_factory] = lambda: (provider_factory or provider_for_question)
    return TestClient(app, **kwargs)


@pytest.fixture(scope="module")
def client(ctx: ToolContext) -> TestClient:
    return make_client(ctx)


def assert_error(response, status: int, error_type: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"} and body["error"]["type"] == error_type and body["error"]["message"]
    assert "Traceback" not in response.text and 'File "' not in response.text
    return body["error"]


# ----------------------------------------------------------------- health and docs


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "service": "risksignal", "version": __version__, "database_available": True,
        "llm_provider": "mock", "llm_configured": True,
        "data_notice": "All data are synthetic (fictional Atlas Bank). Model parameters are illustrative.",
    }


def test_health_reports_a_missing_database_as_degraded(tmp_path: Path) -> None:
    missing = ToolContext(db_path=tmp_path / "missing.db")
    body = make_client(missing).get("/health").json()
    assert body["status"] == "degraded" and body["database_available"] is False
    assert not (tmp_path / "missing.db").exists()


def test_health_never_reveals_the_api_key(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    body = make_client(ctx, provider_name="anthropic").get("/health")
    assert body.json()["llm_configured"] is True and "sk-test" not in body.text
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert make_client(ctx, provider_name="anthropic").get("/health").json()["llm_configured"] is False


def test_interactive_docs_and_openapi_schema_work(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200 and "swagger" in docs.text.lower() and "/openapi.json" in docs.text
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    spec = schema.json()
    assert spec["info"]["title"] == "RiskSignal API" and spec["info"]["version"] == __version__
    assert "synthetic" in spec["info"]["description"].lower() and "not forecasts" in spec["info"]["description"]
    expected = {
        ("get", "/health"), ("get", "/overview"), ("get", "/systems"), ("get", "/systems/{system_id}"),
        ("get", "/systems/{system_id}/incidents"), ("get", "/systems/{system_id}/controls"),
        ("get", "/systems/{system_id}/dependencies"), ("get", "/systems/{system_id}/kri"),
        ("post", "/simulations"), ("get", "/scenarios"), ("post", "/scenarios/compare"),
        ("post", "/scenarios/compare-custom"), ("post", "/agent/investigate"), ("post", "/agent/chat"),
    }
    assert {(m, p) for p, ops in spec["paths"].items() for m in ops} == expected
    for ops in spec["paths"].values():
        for operation in ops.values():
            assert operation["summary"] and operation["responses"]["200"]


def test_documented_error_responses(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/systems/{system_id}"]["get"]
    assert {"404", "422", "503"} <= set(operation["responses"])


# ----------------------------------------------------------------- systems


def test_list_systems(client: TestClient) -> None:
    body = client.get("/systems").json()
    assert body["ok"] is True and body["data_kind"] == "observed_synthetic_data" and "synthetic" in body["notice"].lower()
    systems = body["systems"]
    assert len(systems) == 20 and [s["system_id"] for s in systems] == sorted(s["system_id"] for s in systems)
    focal = next(s for s in systems if s["system_id"] == FOCAL)
    assert focal == {"system_id": FOCAL, "name": "Payment Engine 01", "criticality": "critical",
                     "primary_process_id": "P01", "primary_process_name": "International Payments"}


def test_system_profile(client: TestClient) -> None:
    body = client.get(f"/systems/{FOCAL}").json()
    assert body["system"]["system_id"] == FOCAL and body["primary_process"]["name"] == "International Payments"
    assert body["metadata"]["number_of_controls"] == 4 and body["data_kind"] == "observed_synthetic_data"


def test_incidents(client: TestClient, ctx: ToolContext) -> None:
    body = client.get(f"/systems/{FOCAL}/incidents").json()
    assert body["months"] == 12 and body["counts"]["total"] == len(body["incidents"]) >= 3
    assert body["counts"]["deployment_keyword_matches"] >= 2
    longer = client.get(f"/systems/{FOCAL}/incidents", params={"months": 60}).json()
    assert longer["months"] == 60 and longer["counts"]["total"] > body["counts"]["total"]


def test_controls(client: TestClient) -> None:
    body = client.get(f"/systems/{FOCAL}/controls").json()
    assert len(body["controls"]) == 4 and len(body["overdue_control_ids"]) == 1
    assert {c["review_status"] for c in body["controls"]} <= {"current", "due", "overdue"}


def test_dependencies_show_the_shared_vendor(client: TestClient) -> None:
    body = client.get(f"/systems/{FOCAL}/dependencies").json()
    assert {v["vendor_id"] for v in body["vendors"]} == {"V02", "V04"}
    v04 = next(s for s in body["shared_vendors"] if s["vendor"]["vendor_id"] == "V04")
    assert [o["system_id"] for o in v04["other_systems"]] == ["PAYMENT_ENGINE_02"]
    assert any(r["system"]["system_id"] == "PAYMENT_ENGINE_02" for r in body["related_systems"])
    assert body["supported_processes"][0]["process_id"] == "P01" and len(body["controls"]["controls"]) == 4


def test_kri(client: TestClient) -> None:
    body = client.get(f"/systems/{FOCAL}/kri", params={"months": 6}).json()
    assert len(body["series"]) == 5 and all(len(s["observations"]) == 6 for s in body["series"])


@pytest.mark.parametrize("path", ["", "/incidents", "/controls", "/dependencies", "/kri"])
def test_unknown_system_is_404_with_suggestions(client: TestClient, path: str) -> None:
    error = assert_error(client.get(f"/systems/PAYMENT_ENGINE_99{path}"), 404, "unknown_system")
    assert "PAYMENT_ENGINE_99" in error["message"] and "PAYMENT_ENGINE_01" in error["suggestions"]


def test_lowercase_system_id_is_not_silently_accepted(client: TestClient) -> None:
    error = assert_error(client.get("/systems/payment_engine_01"), 404, "unknown_system")
    assert error["suggestions"][0] == FOCAL


@pytest.mark.parametrize("months", ["0", "-3", "121", "abc", "1.5"])
@pytest.mark.parametrize("path", ["incidents", "kri"])
def test_invalid_months_is_422(client: TestClient, path: str, months: str) -> None:
    error = assert_error(client.get(f"/systems/{FOCAL}/{path}", params={"months": months}), 422, "validation_error")
    assert error["details"][0]["field"] == "query.months"


def test_sql_injection_in_path_is_just_an_unknown_system(client: TestClient, ctx: ToolContext) -> None:
    assert_error(client.get("/systems/x'; DROP TABLE incidents; --"), 404, "unknown_system")
    assert ctx.query("SELECT COUNT(*) AS n FROM incidents")[0]["n"] > 0


def test_unknown_route_and_wrong_method_use_the_error_format(client: TestClient) -> None:
    assert_error(client.get("/nothing-here"), 404, "http_error")
    assert_error(client.post("/systems"), 405, "http_error")


def test_data_endpoints_call_the_tool_layer(ctx: ToolContext) -> None:
    for name, url in [("get_system_profile", f"/systems/{FOCAL}"), ("get_controls", f"/systems/{FOCAL}/controls"),
                      ("get_dependencies", f"/systems/{FOCAL}/dependencies")]:
        with mock.patch(f"risksignal.api.routes_systems.{name}", wraps=getattr(routes_systems, name)) as spy:
            assert make_client(ctx).get(url).status_code == 200
        spy.assert_called_once_with(ctx, FOCAL)
    with mock.patch("risksignal.api.routes_systems.get_recent_incidents", wraps=routes_systems.get_recent_incidents) as spy:
        make_client(ctx).get(f"/systems/{FOCAL}/incidents", params={"months": 9})
    spy.assert_called_once_with(ctx, FOCAL, 9)


# ----------------------------------------------------------------- simulations


def test_simulation_returns_the_tool_result_unchanged(client: TestClient, ctx: ToolContext) -> None:
    body = client.post("/simulations", json={"system_id": FOCAL, "number_of_simulations": 20_000, "random_seed": 7}).json()
    direct = json.loads(run_loss_simulation(ctx, FOCAL, 20_000, 7).model_dump_json())
    assert body == direct
    assert body["data_kind"] == "modelled_output" and body["model_assumptions"]["random_seed"] == 7
    metrics = body["simulation_results"]["metrics"]
    assert metrics["median"] <= metrics["p95"] <= metrics["p99"] and metrics["expected_shortfall_95"] >= metrics["p95"]
    assert len(body["simulation_results"]["histogram"]["counts"]) == 50


def test_simulation_defaults_and_determinism(client: TestClient) -> None:
    first = client.post("/simulations", json={"system_id": FOCAL}).json()
    assert (first["model_assumptions"]["number_of_simulations"], first["model_assumptions"]["random_seed"]) == (100_000, 42)
    assert client.post("/simulations", json={"system_id": FOCAL}).json() == first
    other = client.post("/simulations", json={"system_id": FOCAL, "random_seed": 43}).json()
    assert other["simulation_results"]["metrics"] != first["simulation_results"]["metrics"]


def test_simulation_endpoint_calls_the_tool_with_the_request_values(ctx: ToolContext) -> None:
    with mock.patch("risksignal.api.routes_simulation.run_loss_simulation", wraps=routes_simulation.run_loss_simulation) as spy:
        make_client(ctx).post("/simulations", json={"system_id": FOCAL, "number_of_simulations": 5_000, "random_seed": 3})
    spy.assert_called_once_with(ctx, FOCAL, 5_000, 3)


@pytest.mark.parametrize("payload", [
    {},
    {"system_id": ""},
    {"system_id": FOCAL, "number_of_simulations": 999},
    {"system_id": FOCAL, "number_of_simulations": 1_000_001},
    {"system_id": FOCAL, "number_of_simulations": "100000"},
    {"system_id": FOCAL, "number_of_simulations": 5000.5},
    {"system_id": FOCAL, "number_of_simulations": True},
    {"system_id": FOCAL, "random_seed": -1},
    {"system_id": FOCAL, "random_seed": 2**32},
    {"system_id": FOCAL, "random_seed": "7"},
    {"system_id": 123},
    {"system_id": FOCAL, "lambda_override": 5.0},
])
def test_invalid_simulation_parameters_are_422(client: TestClient, payload: dict) -> None:
    assert_error(client.post("/simulations", json=payload), 422, "validation_error")


def test_simulation_with_malformed_json_is_422(client: TestClient) -> None:
    assert_error(client.post("/simulations", content="{not json", headers={"content-type": "application/json"}),
                 422, "validation_error")


def test_simulation_for_unknown_system_is_404(client: TestClient) -> None:
    assert_error(client.post("/simulations", json={"system_id": "NOPE_99"}), 404, "unknown_system")


def test_scenario_comparison_returns_the_tool_result_unchanged(client: TestClient, ctx: ToolContext) -> None:
    payload = {"system_id": FOCAL, "scenario_id": "SHARED_VENDOR_OUTAGE", "number_of_simulations": 20_000, "random_seed": 5}
    body = client.post("/scenarios/compare", json=payload).json()
    assert body == json.loads(compare_baseline_and_stress(ctx, FOCAL, "SHARED_VENDOR_OUTAGE", 20_000, 5).model_dump_json())
    results = body["simulation_results"]
    assert results["stress_metrics"]["p95"] > results["baseline_metrics"]["p95"]
    assert results["percentage_differences"]["p95"] > 0 and results["absolute_differences"]["p95"] > 0
    stress = body["stress_assumptions"]
    assert stress["scenario"]["provenance"] == "predefined_illustrative" and "illustrative" in stress["label"]
    assert body["baseline_assumptions"]["lambda_source"] == "system_history"


def test_scenario_endpoint_calls_the_tool(ctx: ToolContext) -> None:
    with mock.patch("risksignal.api.routes_simulation.compare_baseline_and_stress",
                    wraps=routes_simulation.compare_baseline_and_stress) as spy:
        make_client(ctx).post("/scenarios/compare", json={"system_id": FOCAL, "scenario_id": "SHARED_VENDOR_OUTAGE"})
    spy.assert_called_once_with(ctx, FOCAL, "SHARED_VENDOR_OUTAGE", 100_000, 42)


def test_unknown_scenario_is_404_with_the_available_ones(client: TestClient) -> None:
    error = assert_error(client.post("/scenarios/compare", json={"system_id": FOCAL, "scenario_id": "MADE_UP"}),
                         404, "unknown_scenario")
    assert error["suggestions"] == ["SHARED_VENDOR_OUTAGE"]


def test_scenario_for_unknown_system_and_bad_parameters(client: TestClient) -> None:
    assert_error(client.post("/scenarios/compare", json={"system_id": "NOPE_99", "scenario_id": "SHARED_VENDOR_OUTAGE"}),
                 404, "unknown_system")
    assert_error(client.post("/scenarios/compare", json={"system_id": FOCAL}), 422, "validation_error")
    assert_error(client.post("/scenarios/compare", json={"system_id": FOCAL, "scenario_id": "X", "number_of_simulations": 1}),
                 422, "validation_error")
    # users cannot supply their own scenario numbers through the API
    assert_error(client.post("/scenarios/compare", json={"system_id": FOCAL, "scenario_id": "SHARED_VENDOR_OUTAGE",
                                                         "lambda_multiplier": 9}), 422, "validation_error")


# ----------------------------------------------------------------- overview and scenarios (used by the UI)


def test_overview_counts_and_recent_incidents(client: TestClient, ctx: ToolContext) -> None:
    body = client.get("/overview").json()
    counts = body["counts"]
    assert (counts["systems"], counts["processes"], counts["vendors"], counts["controls"]) == (20, 10, 8, 40)
    assert counts["incidents"] == ctx.query("SELECT COUNT(*) AS n FROM incidents")[0]["n"] > 250
    assert counts["overdue_controls"] == ctx.query(
        "SELECT COUNT(*) AS n FROM controls WHERE review_status = 'overdue'"
    )[0]["n"]
    assert counts["total_recorded_loss"] == pytest.approx(
        ctx.query("SELECT SUM(financial_loss) AS total FROM incidents")[0]["total"]
    )
    assert counts["kri_observations"] > 5000 and counts["data_window_end"] == "2026-09-30"
    recent = body["recent_incidents"]
    assert len(recent) == 10 and [i["date"] for i in recent] == sorted((i["date"] for i in recent), reverse=True)
    assert all(i["system_name"] and i["description"] for i in recent) and body["data_kind"] == "observed_synthetic_data"
    assert len(client.get("/overview", params={"recent_incidents": 3}).json()["recent_incidents"]) == 3
    for bad in ("0", "101", "x"):
        assert_error(client.get("/overview", params={"recent_incidents": bad}), 422, "validation_error")


def test_overview_without_a_database_is_503(tmp_path: Path) -> None:
    assert_error(make_client(ToolContext(db_path=tmp_path / "missing.db")).get("/overview"), 503, "data_unavailable")


def test_scenario_list_exposes_the_assumptions_before_running(client: TestClient) -> None:
    body = client.get("/scenarios").json()
    assert body["data_kind"] == "illustrative_assumptions" and "not calibrated" in body["notice"].lower()
    scenario = body["scenarios"][0]
    assert scenario["scenario_id"] == "SHARED_VENDOR_OUTAGE" and scenario["provenance"] == "predefined_illustrative"
    assert (scenario["lambda_multiplier"], scenario["severity_mu_shift"], scenario["severity_sigma_multiplier"]) == (1.8, 0.2, 1.1)
    assert any("ILLUSTRATIVE" in note for note in scenario["assumption_notes"])


def test_custom_scenario_comparison(client: TestClient, ctx: ToolContext) -> None:
    payload = {"system_id": FOCAL, "lambda_multiplier": 1.5, "severity_sigma_multiplier": 1.2,
               "number_of_simulations": 20_000, "random_seed": 4}
    body = client.post("/scenarios/compare-custom", json=payload).json()
    assert body["tool_name"] == "compare_baseline_and_custom_scenario" and body["data_kind"] == "modelled_output"
    base, stress = body["baseline_assumptions"], body["stress_assumptions"]
    assert stress["scenario"]["provenance"] == "user_supplied" and "user-supplied" in stress["label"]
    assert stress["stress_parameters"]["lambda_value"] == pytest.approx(1.5 * base["lambda_used"])
    assert stress["stress_parameters"]["sigma"] == pytest.approx(1.2 * base["severity_sigma"])
    assert stress["stress_parameters"]["mu"] == pytest.approx(base["severity_mu"])  # shift defaults to 0
    assert body["simulation_results"]["stress_metrics"]["p95"] > body["simulation_results"]["baseline_metrics"]["p95"]
    from risksignal.tools.simulation_tools import compare_baseline_and_custom_scenario
    direct = compare_baseline_and_custom_scenario(ctx, FOCAL, 1.5, 0.0, 1.2, 20_000, 4)
    assert body == json.loads(direct.model_dump_json())


def test_neutral_custom_scenario_reproduces_the_baseline(client: TestClient) -> None:
    body = client.post("/scenarios/compare-custom", json={"system_id": FOCAL, "number_of_simulations": 5_000}).json()
    results = body["simulation_results"]
    assert results["stress_metrics"] == results["baseline_metrics"]
    assert all(v == 0 for v in results["absolute_differences"].values())


def test_custom_scenario_endpoint_calls_the_tool(ctx: ToolContext) -> None:
    from risksignal.api import routes_simulation as module
    with mock.patch("risksignal.api.routes_simulation.compare_baseline_and_custom_scenario",
                    wraps=module.compare_baseline_and_custom_scenario) as spy:
        make_client(ctx).post("/scenarios/compare-custom", json={"system_id": FOCAL, "lambda_multiplier": 2})
    spy.assert_called_once_with(ctx, FOCAL, 2, 0.0, 1.0, 100_000, 42)


@pytest.mark.parametrize("numbers", [
    {"lambda_multiplier": 0}, {"lambda_multiplier": -1}, {"lambda_multiplier": 101},
    {"severity_sigma_multiplier": 0}, {"severity_sigma_multiplier": 6}, {"severity_mu_shift": 5.5},
    {"lambda_multiplier": "1.5"}, {"lambda_multiplier": True}, {"lambda_multiplier": None},
])
def test_invalid_custom_numbers_are_422(client: TestClient, numbers: dict) -> None:
    response = client.post("/scenarios/compare-custom", json={"system_id": FOCAL, "number_of_simulations": 1_000, **numbers})
    assert response.status_code == 422 and response.json()["error"]["type"] in ("invalid_argument", "validation_error")
    assert "Traceback" not in response.text


def test_custom_scenario_range_errors_name_the_field(client: TestClient) -> None:
    error = assert_error(client.post("/scenarios/compare-custom", json={"system_id": FOCAL, "lambda_multiplier": 500}),
                         422, "invalid_argument")
    assert "lambda_multiplier" in error["message"]


def test_custom_scenario_unknown_system_and_extra_fields(client: TestClient) -> None:
    assert_error(client.post("/scenarios/compare-custom", json={"system_id": "NOPE_99"}), 404, "unknown_system")
    assert_error(client.post("/scenarios/compare-custom", json={"system_id": FOCAL, "scenario_id": "X"}), 422, "validation_error")


def test_the_agent_cannot_use_the_custom_scenario_tool(client: TestClient) -> None:
    from risksignal.agent.tool_registry import build_default_registry
    assert "compare_baseline_and_custom_scenario" not in build_default_registry(ToolContext()).names


# ----------------------------------------------------------------- agent (mock LLM only)


def test_agent_investigation_with_the_mock_provider(client: TestClient) -> None:
    response = client.post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_01."})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed" and body["provider"] == "mock" and body["llm_calls"] == 3
    for heading in ("Observed evidence", "Model assumptions", "Simulation results", "Connected exposures",
                    "Suggested investigation questions", "Limitations"):
        assert heading in body["final_response"]
    assert body["activity_log"][0] == f"Retrieved system profile for {FOCAL}"
    assert body["activity_log"][-1] == "Ran 100,000 year Monte Carlo simulation (seed 42)"
    assert [a["tool_name"] for a in body["tool_activity"]] == [
        "get_system_profile", "get_recent_incidents", "get_kri_history", "get_controls",
        "get_dependencies", "run_loss_simulation"]
    first = body["tool_activity"][0]
    assert first["status"] == "completed" and first["tool_input"] == {"system_id": FOCAL} and first["started_at"]
    assert body["warnings"] == [] and body["ungrounded_numbers"] == [] and "synthetic" in body["disclaimer"]


def test_agent_response_omits_tool_outputs_unless_asked(client: TestClient) -> None:
    question = {"question": "Investigate PAYMENT_ENGINE_01."}
    plain = client.post("/agent/investigate", json=question).json()
    assert all(a["output"] is None for a in plain["tool_activity"])
    full = client.post("/agent/investigate", json={**question, "include_tool_outputs": True}).json()
    assert all(a["output"]["ok"] is True for a in full["tool_activity"])
    assert len(json.dumps(full)) > len(json.dumps(plain))
    assert full["final_response"] == plain["final_response"]


def test_agent_runs_the_stress_comparison_when_the_question_asks_for_it(client: TestClient) -> None:
    body = client.post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_01 under the vendor outage stress scenario."}).json()
    assert body["tool_activity"][-1]["tool_name"] == "compare_baseline_and_stress"
    assert body["activity_log"][-1].startswith("Compared baseline and stress scenario SHARED_VENDOR_OUTAGE")


def test_agent_reports_an_unknown_system_in_its_answer(client: TestClient) -> None:
    response = client.post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_99."})
    assert response.status_code == 200  # a normal answer: the agent explains the problem
    body = response.json()
    assert [(a["tool_name"], a["status"], a["error_type"]) for a in body["tool_activity"]] == [
        ("get_system_profile", "failed", "unknown_system")]
    assert "could not complete" in body["final_response"] and "PAYMENT_ENGINE_01" in body["final_response"]


def test_agent_endpoint_runs_the_investigator_with_the_injected_provider(ctx: ToolContext) -> None:
    with mock.patch("risksignal.api.routes_agent.Investigator", wraps=routes_agent.Investigator) as spy:
        make_client(ctx).post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_02."})
    spy.assert_called_once()
    provider = spy.call_args.args[0]
    assert provider.name == "mock"


def test_numbers_the_model_invents_are_surfaced_to_the_ui(ctx: ToolContext) -> None:
    lie = MockProvider([LLMResponse(text="Baseline P95 annual loss is 1,234,567.")])
    client = make_client(ctx, provider_factory=lambda question: lie)
    body = client.post("/agent/investigate", json={"question": "What is the P95 for PAYMENT_ENGINE_01?"}).json()
    assert body["ungrounded_numbers"] == ["1,234,567"] and body["warnings"]


def test_a_question_without_a_system_gets_a_clarification_from_the_mock(client: TestClient) -> None:
    body = client.post("/agent/investigate", json={"question": "What is the riskiest system?"}).json()
    assert "Please name the system" in body["final_response"] and body["tool_activity"] == []


@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "hi"}, {"question": "x" * 2001},
                                      {"question": 5}, {"question": "Investigate PAYMENT_ENGINE_01.", "extra": 1},
                                      {"question": "Investigate PAYMENT_ENGINE_01.", "include_tool_outputs": "yes"}])
def test_invalid_agent_requests_are_422(client: TestClient, payload: dict) -> None:
    assert_error(client.post("/agent/investigate", json=payload), 422, "validation_error")


def test_language_model_not_configured_is_503(ctx: ToolContext) -> None:
    def not_configured(question: str):
        raise LLMProviderError("ANTHROPIC_API_KEY is not set.")

    error = assert_error(make_client(ctx, provider_factory=not_configured).post(
        "/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_01."}), 503, "llm_unavailable")
    assert "ANTHROPIC_API_KEY" in error["message"]


def test_language_model_failure_during_a_run_is_503(ctx: ToolContext) -> None:
    client = make_client(ctx, provider_factory=lambda question: MockProvider([]))
    assert_error(client.post("/agent/investigate", json={"question": "Investigate PAYMENT_ENGINE_01."}), 503, "llm_unavailable")


def test_default_provider_selection_follows_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("risksignal.api.dependencies.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for value, expected in [("mock", "mock"), (None, "anthropic"), ("MOCK", "mock")]:
        get_settings.cache_clear()
        if value is None:
            monkeypatch.delenv("RISKSIGNAL_LLM_PROVIDER", raising=False)
        else:
            monkeypatch.setenv("RISKSIGNAL_LLM_PROVIDER", value)
        assert get_settings().llm_provider == expected
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("RISKSIGNAL_LLM_PROVIDER", "mock")
        assert get_provider_factory()("Investigate PAYMENT_ENGINE_01.").name == "mock"

        get_settings.cache_clear()
        monkeypatch.setenv("RISKSIGNAL_LLM_PROVIDER", "anthropic")
        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):  # no key: fails before any network use
            get_provider_factory()("q")

        get_settings.cache_clear()
        monkeypatch.setenv("RISKSIGNAL_LLM_PROVIDER", "bogus")
        with pytest.raises(LLMProviderError, match="Unknown RISKSIGNAL_LLM_PROVIDER"):
            get_provider_factory()("q")
    finally:
        get_settings.cache_clear()


def test_database_path_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("risksignal.api.dependencies.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("RISKSIGNAL_DB_PATH", str(tmp_path / "custom.db"))
    get_settings.cache_clear()
    try:
        assert get_settings().db_path == tmp_path / "custom.db"
    finally:
        get_settings.cache_clear()


# ----------------------------------------------------------------- failures never leak internals


def test_database_missing_gives_503_not_a_stack_trace(tmp_path: Path) -> None:
    client = make_client(ToolContext(db_path=tmp_path / "missing.db"))
    error = assert_error(client.get(f"/systems/{FOCAL}"), 503, "data_unavailable")
    assert "python -m risksignal.data.generator" in error["message"]
    assert_error(client.get("/systems"), 503, "data_unavailable")


def test_unexpected_exceptions_become_a_generic_500(ctx: ToolContext) -> None:
    app = create_app()

    def explode() -> ToolContext:
        raise RuntimeError("secret internal detail at /home/x.py line 42")

    app.dependency_overrides[get_tool_context] = explode
    response = TestClient(app, raise_server_exceptions=False).get(f"/systems/{FOCAL}")
    error = assert_error(response, 500, "internal_error")
    assert "secret" not in response.text and error["message"] == "Internal server error."


# ----------------------------------------------------------------- structure


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def test_api_contains_no_business_logic_imports() -> None:
    forbidden = ("sqlite3", "numpy", "scipy", "pandas", "networkx", "anthropic",
                 "risksignal.stochastic", "risksignal.graph", "risksignal.data.generator", "risksignal.data.schemas")
    for path in (SRC / "api").glob("*.py"):
        found = [n for n in _imports(path) if any(n == f or n.startswith(f + ".") for f in forbidden)]
        assert not found, f"{path.name}: {found}"


def test_lower_layers_do_not_import_the_api() -> None:
    for package in ("data", "stochastic", "graph", "tools", "agent"):
        for path in (SRC / package).glob("*.py"):
            assert not [n for n in _imports(path) if n.startswith("risksignal.api")], path.name


def test_api_module_uses_the_documented_entry_point() -> None:
    from risksignal.api.main import app

    assert app.title == "RiskSignal API" and dependencies.PROVIDERS == ("anthropic", "mock")
