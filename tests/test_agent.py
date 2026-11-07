"""Tests for the investigation agent. No test contacts the Anthropic API."""

import ast
import datetime as dt
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest

from risksignal.agent.anthropic_provider import (
    DEFAULT_MODEL,
    AnthropicProvider,
    parse_response,
    to_anthropic_messages,
    to_anthropic_tools,
)
from risksignal.agent.base import (
    LLMMessage,
    LLMProviderError,
    LLMResponse,
    ToolCall,
    ToolResultBlock,
    ToolSpec,
)
from risksignal.agent.investigator import Investigator, find_ungrounded_numbers, main
from risksignal.agent.mock_provider import (
    MockProvider,
    investigation_script,
    provider_for_question,
    results_by_tool,
    tool_request,
)
from risksignal.agent.prompts import SYSTEM_PROMPT
from risksignal.agent.schemas import InvestigationResult, ToolActivity
from risksignal.agent.tool_registry import ToolDefinition, ToolRegistry, build_default_registry
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.tools.schemas import ToolError
from risksignal.tools.simulation_tools import run_loss_simulation

FOCAL = "PAYMENT_ENGINE_01"
SRC = Path(__file__).resolve().parents[1] / "src" / "risksignal"
ALL_TOOL_NAMES = {"get_system_profile", "get_recent_incidents", "get_kri_history", "get_controls",
                  "get_dependencies", "run_loss_simulation", "compare_baseline_and_stress",
                  "get_kri_monitoring", "get_model_diagnostics", "get_risk_workpaper"}


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("agent_db")))


@pytest.fixture(scope="module")
def registry(ctx: ToolContext) -> ToolRegistry:
    return build_default_registry(ctx)


@pytest.fixture(scope="module")
def full_run(registry: ToolRegistry) -> tuple[InvestigationResult, MockProvider]:
    provider = investigation_script(FOCAL, include_simulation=True)
    return Investigator(provider, registry).investigate("Investigate PAYMENT_ENGINE_01."), provider


def activity(name: str, tool_input: dict[str, Any], output: dict[str, Any]) -> ToolActivity:
    return ToolActivity(step=1, tool_name=name, tool_input=tool_input, status="completed", summary="s",
                        started_at=dt.datetime.now(dt.timezone.utc), duration_ms=1.0, output=output)


def find_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(find_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(find_key(v, key) for v in value)
    return False


# ----------------------------------------------------------------- tool registry


def test_registry_publishes_investigation_and_workbench_tools(registry: ToolRegistry) -> None:
    specs = registry.specs()
    assert {s.name for s in specs} == ALL_TOOL_NAMES and len(specs) == 10
    for spec in specs:
        assert spec.description and spec.input_schema["type"] == "object"
        assert "system_id" in spec.input_schema["required"]
        assert spec.input_schema["additionalProperties"] is False
        json.dumps(spec.input_schema)
    stress = next(s for s in specs if s.name == "compare_baseline_and_stress")
    assert stress.input_schema["properties"]["scenario_id"]["enum"] == ["SHARED_VENDOR_OUTAGE"]
    assert "scenario_id" in stress.input_schema["required"]


def test_registry_runs_the_real_tool_and_writes_the_log_line_in_python(registry: ToolRegistry) -> None:
    outcome = registry.run("get_recent_incidents", {"system_id": FOCAL, "months": 12})
    assert outcome.ok and outcome.error_type is None
    assert outcome.summary == f"Retrieved 12 months of incidents ({outcome.result.counts.total} found)"
    assert json.loads(outcome.content) == outcome.output
    assert outcome.output["counts"]["total"] == outcome.result.counts.total


def test_activity_log_lines_follow_the_requested_style(registry: ToolRegistry) -> None:
    assert registry.run("get_system_profile", {"system_id": FOCAL}).summary == f"Retrieved system profile for {FOCAL}"
    simulation = registry.run("run_loss_simulation", {"system_id": FOCAL, "number_of_simulations": 100_000})
    assert simulation.summary == "Ran 100,000 year Monte Carlo simulation (seed 42)"
    assert registry.run("get_dependencies", {"system_id": FOCAL}).summary.startswith("Checked system dependencies")


def test_model_view_omits_bulky_histograms_but_keeps_all_numbers(registry: ToolRegistry) -> None:
    outcome = registry.run("run_loss_simulation", {"system_id": FOCAL})
    assert outcome.result.simulation_results.histogram is not None  # the full result keeps it
    assert not find_key(outcome.output, "histogram") and "histogram" not in outcome.content
    assert outcome.output["simulation_results"]["metrics"]["p95"] == outcome.result.simulation_results.metrics.p95
    stress = registry.run("compare_baseline_and_stress", {"system_id": FOCAL, "scenario_id": "SHARED_VENDOR_OUTAGE"})
    assert not find_key(stress.output, "baseline_histogram") and not find_key(stress.output, "stress_histogram")


@pytest.mark.parametrize("name, arguments, fragment", [
    ("run_sql", {"query": "DROP TABLE incidents"}, "Unknown tool 'run_sql'"),
    ("get_controls", {}, "Missing required argument(s): system_id"),
    ("get_controls", {"system_id": FOCAL, "limit": 5}, "Unexpected argument(s): limit"),
    ("get_controls", "PAYMENT_ENGINE_01", "must be a JSON object"),
    ("get_recent_incidents", {"system_id": FOCAL, "months": "12"}, "months must be an integer"),
])
def test_bad_model_requests_become_failed_outcomes_not_exceptions(
    registry: ToolRegistry, name: str, arguments: Any, fragment: str
) -> None:
    outcome = registry.run(name, arguments)
    assert not outcome.ok and outcome.error_type == "invalid_argument"
    assert isinstance(outcome.result, ToolError) and fragment in outcome.result.message
    assert outcome.summary.startswith(f"{name} failed")


def test_tool_errors_pass_through_with_their_type(registry: ToolRegistry) -> None:
    outcome = registry.run("get_system_profile", {"system_id": "PAYMENT_ENGINE_99"})
    assert not outcome.ok and outcome.error_type == "unknown_system"
    assert "PAYMENT_ENGINE_01" in outcome.output["suggestions"]


def test_registry_run_survives_a_tool_that_crashes() -> None:
    def crash(**kwargs: Any) -> None:
        raise RuntimeError("secret internal detail")

    broken = ToolRegistry([ToolDefinition("crash", "d", {"type": "object", "properties": {}, "required": []},
                                          crash, lambda a, r: "x")])
    outcome = broken.run("crash", {})
    assert not outcome.ok and outcome.error_type == "internal_error"
    assert "secret" not in outcome.content


# ----------------------------------------------------------------- the agent calls tools


def test_investigation_calls_the_expected_tools_and_records_them(full_run: tuple[InvestigationResult, MockProvider]) -> None:
    result, _ = full_run
    assert result.status == "completed" and result.llm_calls == 3 and result.provider == "mock"
    assert [a.tool_name for a in result.tool_activity] == [
        "get_system_profile", "get_recent_incidents", "get_kri_monitoring", "get_controls",
        "get_dependencies", "run_loss_simulation"]  # no stress scenario: it was not requested
    assert [a.step for a in result.tool_activity] == [1, 2, 3, 4, 5, 6]
    assert all(a.status == "completed" and a.error_type is None for a in result.tool_activity)
    assert result.tool_activity[1].tool_input == {"system_id": FOCAL, "months": 12}
    assert result.tool_activity[5].tool_input["random_seed"] == 42
    for a in result.tool_activity:
        assert a.started_at.tzinfo is not None and a.duration_ms >= 0 and a.output["ok"] is True


@pytest.mark.parametrize("question,simulation_tool", [
    (f"Investigate {FOCAL}.", None),
    (f"Simulate annual losses for {FOCAL}.", "run_loss_simulation"),
    (f"Investigate {FOCAL} with stress.", "compare_baseline_and_stress"),
])
def test_simulation_is_optional_and_findings_are_capped_and_source_linked(
    registry: ToolRegistry, question: str, simulation_tool: str | None,
) -> None:
    result = Investigator(provider_for_question(question), registry).investigate(question)
    names = [activity.tool_name for activity in result.tool_activity]
    assert result.status == "completed" and result.ungrounded_numbers == []
    if simulation_tool:
        assert simulation_tool in names
    else:
        assert not {"run_loss_simulation", "compare_baseline_and_stress"} & set(names)
    for heading, following in (("Key Findings", "Next Investigations"), ("Next Investigations", "Limitations")):
        body = result.final_answer.split(heading + "\n")[1].split("\n" + following)[0].split("\nModel assumptions")[0]
        items = [line for line in body.splitlines() if line.startswith("- ")]
        assert 1 <= len(items) <= 3
        assert all("(#supporting-evidence)" in line for line in items)
    assert "vendors:V04" in result.final_answer


def test_activity_log_is_concise_and_ui_ready(full_run: tuple[InvestigationResult, MockProvider]) -> None:
    log = full_run[0].activity_log()
    assert log[0] == f"Retrieved system profile for {FOCAL}"
    assert log[1].startswith("Retrieved 12 months of incidents")
    assert log[-1] == "Ran 100,000 year Monte Carlo simulation (seed 42)"
    assert all(len(line) <= 160 for line in log)


def test_model_receives_tool_results_system_prompt_and_all_read_only_tools(
    full_run: tuple[InvestigationResult, MockProvider]
) -> None:
    _, provider = full_run
    assert len(provider.calls) == 3
    for call in provider.calls:
        assert call["system"] == SYSTEM_PROMPT and set(call["tool_names"]) == ALL_TOOL_NAMES
    seen = results_by_tool(provider.calls[1]["messages"])
    assert seen["get_system_profile"]["system"]["system_id"] == FOCAL  # tool output fed back to the model
    assert set(results_by_tool(provider.calls[2]["messages"])) == {
        "get_system_profile", "get_recent_incidents", "get_kri_monitoring", "get_controls",
        "get_dependencies", "run_loss_simulation"}


def test_answer_is_sectioned_and_every_number_comes_from_a_tool(
    full_run: tuple[InvestigationResult, MockProvider], ctx: ToolContext
) -> None:
    result, _ = full_run
    for heading in ("Investigation Summary", "Key Findings", "Model assumptions", "Simulation results",
                    "Next Investigations", "Limitations"):
        assert heading in result.final_answer
    direct = run_loss_simulation(ctx, FOCAL).simulation_results.metrics  # same call, made independently
    assert f"P95 {direct.p95:,.0f}" in result.final_answer
    assert f"ES99 {direct.expected_shortfall_99:,.0f}" in result.final_answer
    assert result.ungrounded_numbers == [] and result.warnings == []
    assert "synthetic" in result.final_answer.lower() and "not a forecast" in result.final_answer


def test_stress_comparison_is_only_run_when_the_plan_requests_it(registry: ToolRegistry) -> None:
    result = Investigator(investigation_script(FOCAL, include_stress=True), registry).investigate("Investigate with stress.")
    assert result.tool_activity[-1].tool_name == "compare_baseline_and_stress"
    assert result.tool_activity[-1].summary.startswith("Compared baseline and stress scenario SHARED_VENDOR_OUTAGE")
    assert "illustrative assumptions, not calibrated" in result.final_answer and result.ungrounded_numbers == []


def test_result_is_json_serialisable(full_run: tuple[InvestigationResult, MockProvider]) -> None:
    result = full_run[0]
    assert InvestigationResult.model_validate_json(result.model_dump_json()) == result
    assert "synthetic" in result.disclaimer


# ----------------------------------------------------------------- the agent cannot invent numbers


def test_invented_simulation_numbers_are_flagged(registry: ToolRegistry) -> None:
    lie = LLMResponse(text="Simulation results\n- Baseline P95 annual loss is 1,234,567 and ES99 is 9,876,543.")
    result = Investigator(MockProvider([lie]), registry).investigate("What is the loss at risk for PAYMENT_ENGINE_01?")
    assert result.tool_activity == []  # no tool was called, so no number is grounded
    assert result.ungrounded_numbers == ["1,234,567", "9,876,543"]
    assert any("could not be matched" in w for w in result.warnings)


def test_a_tampered_tool_number_is_flagged(registry: ToolRegistry) -> None:
    def tampered(messages: list[LLMMessage]) -> LLMResponse:
        p95 = results_by_tool(messages)["run_loss_simulation"]["simulation_results"]["metrics"]["p95"]
        return LLMResponse(text=f"- Baseline P95 {p95 * 1.5:,.0f}")  # model 'adjusts' a tool value

    steps = [LLMResponse(tool_calls=[tool_request("a", "run_loss_simulation", system_id=FOCAL)], stop_reason="tool_use"), tampered]
    result = Investigator(MockProvider(steps), registry).investigate("Run a simulation.")
    assert len(result.ungrounded_numbers) == 1 and result.status == "completed"


def test_rounded_tool_numbers_are_accepted(registry: ToolRegistry) -> None:
    def rounded(messages: list[LLMMessage]) -> LLMResponse:
        p95 = results_by_tool(messages)["run_loss_simulation"]["simulation_results"]["metrics"]["p95"]
        return LLMResponse(text=f"- P95 is about {p95 / 1e6:.1f} million, or {p95 / 1e3:.0f}K, or {p95:,.0f}.")

    steps = [LLMResponse(tool_calls=[tool_request("a", "run_loss_simulation", system_id=FOCAL)], stop_reason="tool_use"), rounded]
    assert Investigator(MockProvider(steps), registry).investigate("Run a simulation.").ungrounded_numbers == []


def test_grounding_check_rules() -> None:
    acts = [activity("t", {"months": 12}, {"p95": 896435.3, "pct": 154.14, "note": "19 incidents on 2026-09-30", "neg": -42.5})]
    assert find_ungrounded_numbers("P95 is 896,435 (896K, 0.9 million) and +154%, 154.1%, -42.5.", acts) == []
    assert find_ungrounded_numbers("P95 is 950,000.", acts) == ["950,000"]
    assert find_ungrounded_numbers("Loss was 2.3 million.", acts) == ["2.3 million"]
    assert find_ungrounded_numbers("There were 19 incidents in 12 months.", acts) == []
    assert find_ungrounded_numbers("There were 77 incidents.", acts) == ["77"]
    # ignored: identifiers, ISO dates, list numbering, small whole numbers
    text = "1. PAYMENT_ENGINE_01 and V04 on 2025-01-01: P95 and ES99, about 1 in 20 years, 3 systems"
    assert find_ungrounded_numbers(text, acts) == []
    assert find_ungrounded_numbers("Percent change 50%.", acts) == ["50%"]  # small numbers with % are still checked
    assert find_ungrounded_numbers("", acts) == []


# ----------------------------------------------------------------- unknown systems and tool failures


def test_unknown_system_is_reported_without_guessing_or_further_tool_calls(registry: ToolRegistry) -> None:
    provider = investigation_script("PAYMENT_ENGINE_99")
    result = Investigator(provider, registry).investigate("Investigate PAYMENT_ENGINE_99.")
    assert result.status == "completed" and result.llm_calls == 2
    assert [(a.tool_name, a.status, a.error_type) for a in result.tool_activity] == [
        ("get_system_profile", "failed", "unknown_system")]
    assert "could not complete" in result.final_answer and "PAYMENT_ENGINE_01" in result.final_answer
    assert result.activity_log()[0].startswith("get_system_profile failed (unknown_system)")
    assert result.ungrounded_numbers == []


def test_failed_tool_is_returned_to_the_model_flagged_as_an_error(registry: ToolRegistry) -> None:
    steps = [
        LLMResponse(tool_calls=[tool_request("a", "get_recent_incidents", system_id=FOCAL, months=0)], stop_reason="tool_use"),
        LLMResponse(text="The incident tool rejected my request, so I cannot report incidents."),
    ]
    provider = MockProvider(steps)
    result = Investigator(provider, registry).investigate("Show incidents.")
    assert result.status == "completed"
    assert [(a.status, a.error_type) for a in result.tool_activity] == [("failed", "invalid_argument")]
    returned = provider.calls[1]["messages"][-1].tool_results[0]
    assert returned.is_error is True and "months must be between" in returned.content


def test_missing_database_is_handled_as_tool_failures(tmp_path: Path) -> None:
    registry = build_default_registry(ToolContext(db_path=tmp_path / "missing.db"))
    result = Investigator(investigation_script(FOCAL), registry).investigate("Investigate PAYMENT_ENGINE_01.")
    assert result.status == "completed"
    assert result.tool_activity[0].error_type == "data_unavailable" and len(result.tool_activity) == 1
    assert not (tmp_path / "missing.db").exists()


def test_a_tool_the_model_invents_is_refused_and_the_agent_continues(registry: ToolRegistry) -> None:
    steps = [
        LLMResponse(tool_calls=[tool_request("a", "run_sql", query="SELECT * FROM incidents")], stop_reason="tool_use"),
        LLMResponse(text="I have no tool for raw database queries."),
    ]
    result = Investigator(MockProvider(steps), registry).investigate("Run SQL for me.")
    assert result.tool_activity[0].status == "failed" and result.tool_activity[0].error_type == "invalid_argument"
    assert result.final_answer == "I have no tool for raw database queries."


def test_a_tool_failure_in_a_batch_does_not_hide_the_other_results(registry: ToolRegistry) -> None:
    steps = [LLMResponse(tool_calls=[tool_request("a", "get_controls", system_id=FOCAL),
                                     tool_request("b", "get_controls", system_id="NOPE_01")], stop_reason="tool_use"),
             LLMResponse(text="done")]
    result = Investigator(MockProvider(steps), registry).investigate("Controls?")
    assert [a.status for a in result.tool_activity] == ["completed", "failed"]


# ----------------------------------------------------------------- loop safety


def test_step_limit_stops_a_runaway_model(registry: ToolRegistry) -> None:
    forever = LLMResponse(tool_calls=[tool_request("a", "get_controls", system_id=FOCAL)], stop_reason="tool_use")
    provider = MockProvider([forever] * 10)
    result = Investigator(provider, registry, max_steps=3).investigate("Loop.")
    assert result.status == "stopped_max_steps" and result.llm_calls == 3 and len(result.tool_activity) == 3
    assert "stopped after 3 model steps" in result.final_answer and result.warnings


def test_provider_failure_is_reported_not_raised(registry: ToolRegistry) -> None:
    result = Investigator(MockProvider([]), registry).investigate("Investigate PAYMENT_ENGINE_01.")
    assert result.status == "llm_error" and result.llm_calls == 0 and result.tool_activity == []
    assert "could not be used" in result.final_answer


def test_truncated_and_empty_answers_are_warned_about(registry: ToolRegistry) -> None:
    truncated = Investigator(MockProvider([LLMResponse(text="Partial", stop_reason="max_tokens")]), registry).investigate("q")
    assert any("cut off" in w for w in truncated.warnings)
    empty = Investigator(MockProvider([LLMResponse(text="")]), registry).investigate("q")
    assert any("empty" in w for w in empty.warnings)


def test_empty_question_is_rejected(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError):
        Investigator(MockProvider([]), registry).investigate("   ")


def test_question_driven_mock_provider(registry: ToolRegistry) -> None:
    plain = Investigator(provider_for_question("Investigate PAYMENT_ENGINE_02, please."), registry).investigate("Investigate PAYMENT_ENGINE_02, please.")
    assert plain.tool_activity[0].tool_input == {"system_id": "PAYMENT_ENGINE_02"}
    assert "compare_baseline_and_stress" not in [a.tool_name for a in plain.tool_activity]
    for wording in ("Investigate PAYMENT_ENGINE_01 under stress.", "PAYMENT_ENGINE_01: what if the vendor outage happens?"):
        names = [a.tool_name for a in Investigator(provider_for_question(wording), registry).investigate(wording).tool_activity]
        assert names[-1] == "compare_baseline_and_stress"
    forced = provider_for_question("Investigate PAYMENT_ENGINE_01.", include_stress=True)
    assert Investigator(forced, registry).investigate("q").tool_activity[-1].tool_name == "compare_baseline_and_stress"
    # no system named: ask, do not guess
    nothing = Investigator(provider_for_question("Which system is worst?"), registry).investigate("Which system is worst?")
    assert nothing.tool_activity == [] and "Please name the system" in nothing.final_answer


def test_mock_provider_is_deterministic(registry: ToolRegistry) -> None:
    first = Investigator(investigation_script(FOCAL), registry).investigate("Investigate PAYMENT_ENGINE_01.")
    second = Investigator(investigation_script(FOCAL), registry).investigate("Investigate PAYMENT_ENGINE_01.")
    assert first.final_answer == second.final_answer
    assert [a.tool_input for a in first.tool_activity] == [a.tool_input for a in second.tool_activity]


# ----------------------------------------------------------------- the system prompt


@pytest.mark.parametrize("phrase", [
    "Operational Risk investigation assistant", "do not make final risk decisions", "synthetic",
    "Never invent incidents, controls, vendors", "Never calculate quantitative values yourself",
    "NOT forecasts", "JPMorgan", "Investigation Summary", "Model assumptions", "Simulation results",
    "Key Findings", "Next Investigations", "Limitations", "cannot change any records",
    "Do not call any system safe, unsafe",
])
def test_system_prompt_contains_the_required_rules(phrase: str) -> None:
    assert phrase in SYSTEM_PROMPT


# ----------------------------------------------------------------- Anthropic provider (no network)


class FakeAnthropicClient:
    """Stands in for ``anthropic.Anthropic``. Records requests and replays responses."""

    def __init__(self, responses: list[Any]) -> None:
        self.requests: list[dict[str, Any]] = []
        self._responses = list(responses)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def text_block(text: str) -> Any:
    return SimpleNamespace(type="text", text=text)


def tool_block(call_id: str, name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=arguments)


def test_messages_are_converted_to_the_anthropic_format() -> None:
    messages = [
        LLMMessage(role="user", text="Investigate X."),
        LLMMessage(role="assistant", text="Checking.", tool_calls=[ToolCall(id="t1", name="get_controls", arguments={"system_id": "X"})]),
        LLMMessage(role="user", tool_results=[ToolResultBlock(tool_call_id="t1", content='{"ok":true}', is_error=False)]),
        LLMMessage(role="assistant", text=None),  # nothing to send: dropped
    ]
    assert to_anthropic_messages(messages) == [
        {"role": "user", "content": [{"type": "text", "text": "Investigate X."}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Checking."},
                                          {"type": "tool_use", "id": "t1", "name": "get_controls", "input": {"system_id": "X"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"ok":true}', "is_error": False}]},
    ]
    spec = ToolSpec(name="n", description="d", input_schema={"type": "object"})
    assert to_anthropic_tools([spec]) == [{"name": "n", "description": "d", "input_schema": {"type": "object"}}]


def test_responses_are_parsed_into_text_and_tool_calls() -> None:
    parsed = parse_response(SimpleNamespace(content=[text_block("Let me check. "), tool_block("t9", "get_controls", {"system_id": "X"})],
                                            stop_reason="tool_use"))
    assert parsed.text == "Let me check. " and parsed.stop_reason == "tool_use"
    assert parsed.tool_calls == [ToolCall(id="t9", name="get_controls", arguments={"system_id": "X"})]
    assert parse_response(SimpleNamespace(content=[text_block("x")], stop_reason="max_tokens")).stop_reason == "max_tokens"
    assert parse_response(SimpleNamespace(content=[], stop_reason="refusal")).stop_reason == "other"


def test_request_sent_to_the_sdk_has_the_expected_shape() -> None:
    client = FakeAnthropicClient([SimpleNamespace(content=[text_block("hi")], stop_reason="end_turn")])
    provider = AnthropicProvider(model="test-model", client=client)
    spec = ToolSpec(name="n", description="d", input_schema={"type": "object"})
    reply = provider.complete("SYSTEM", [LLMMessage(role="user", text="q")], [spec], 123)
    request = client.requests[0]
    assert request["model"] == "test-model" and request["system"] == "SYSTEM" and request["max_tokens"] == 123
    assert request["tools"][0]["name"] == "n" and "temperature" not in request
    assert reply.text == "hi" and provider.name == "anthropic:test-model"
    hot = AnthropicProvider(model="m", client=FakeAnthropicClient([SimpleNamespace(content=[], stop_reason="end_turn")]), temperature=0.0)
    hot.complete("s", [LLMMessage(role="user", text="q")], [], 10)
    assert hot._client.requests[0]["temperature"] == 0.0


def test_full_investigation_through_the_anthropic_provider_with_a_fake_client(registry: ToolRegistry) -> None:
    client = FakeAnthropicClient([
        SimpleNamespace(content=[text_block("Looking at controls."), tool_block("tu_1", "get_controls", {"system_id": FOCAL})],
                        stop_reason="tool_use"),
        SimpleNamespace(content=[text_block("Observed evidence\n- Four controls are recorded.")], stop_reason="end_turn"),
    ])
    result = Investigator(AnthropicProvider(model="fake-model", client=client), registry).investigate("Controls for PAYMENT_ENGINE_01?")
    assert result.status == "completed" and result.provider == "anthropic:fake-model"
    assert [a.tool_name for a in result.tool_activity] == ["get_controls"]
    second_request = client.requests[1]["messages"]
    assert second_request[-1]["content"][0]["type"] == "tool_result"
    assert second_request[-1]["content"][0]["tool_use_id"] == "tu_1" and second_request[-1]["content"][0]["is_error"] is False
    assert json.loads(second_request[-1]["content"][0]["content"])["system_id"] == FOCAL


def test_sdk_errors_become_provider_errors_without_secrets(registry: ToolRegistry) -> None:
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
    provider = AnthropicProvider(model="m", client=FakeAnthropicClient([error]))
    with pytest.raises(LLMProviderError, match="APIConnectionError"):
        provider.complete("s", [LLMMessage(role="user", text="q")], [], 10)
    result = Investigator(AnthropicProvider(model="m", client=FakeAnthropicClient([error])), registry).investigate("Investigate PAYMENT_ENGINE_01.")
    assert result.status == "llm_error"


def test_api_key_comes_from_the_environment_and_is_never_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("risksignal.agent.anthropic_provider.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    provider = AnthropicProvider()  # builds the SDK client; makes no request
    assert provider.model == DEFAULT_MODEL
    assert "sk-test-not-a-real-key" not in provider.name and "sk-test-not-a-real-key" not in repr(vars(provider).get("model"))
    monkeypatch.setenv("ANTHROPIC_MODEL", "from-env")
    assert AnthropicProvider().model == "from-env" and AnthropicProvider(model="explicit").model == "explicit"


def test_cli_offline_mode_runs_without_an_api_key(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, ctx: ToolContext) -> None:
    monkeypatch.setattr("risksignal.agent.investigator.build_default_registry", lambda: build_default_registry(ctx))
    assert main(["--mock", "Investigate PAYMENT_ENGINE_01."]) == 0
    output = capsys.readouterr().out
    assert "Tool activity:" in output and "Investigation Summary" in output and "Provider: mock" in output


def test_cli_without_a_key_explains_what_to_do(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("risksignal.agent.anthropic_provider.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["Investigate PAYMENT_ENGINE_01."]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out


# ----------------------------------------------------------------- structure and secrets


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def test_only_the_anthropic_provider_depends_on_anthropic() -> None:
    for path in (SRC / "agent").glob("*.py"):
        uses = any(n.split(".")[0] == "anthropic" for n in _imports(path))
        assert uses == (path.name == "anthropic_provider.py"), path.name


def test_agent_has_no_direct_data_or_statistics_access() -> None:
    forbidden = ("sqlite3", "numpy", "scipy", "pandas", "networkx", "risksignal.data", "risksignal.graph",
                 "risksignal.api", "risksignal.ui", "fastapi", "streamlit")
    for path in (SRC / "agent").glob("*.py"):
        found = [n for n in _imports(path) if any(n == f or n.startswith(f + ".") for f in forbidden)]
        assert not found, f"{path.name}: {found}"


def test_lower_layers_do_not_import_the_agent() -> None:
    for package in ("data", "stochastic", "graph", "tools"):
        for path in (SRC / package).glob("*.py"):
            assert not [n for n in _imports(path) if n.startswith("risksignal.agent")], path.name


def test_no_api_keys_in_the_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    key_shape = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
    for pattern in ("src/**/*.py", "tests/**/*.py", "docs/*.md", "README.md", ".env.example"):
        for path in root.glob(pattern):
            assert not key_shape.search(path.read_text(encoding="utf-8")), path
    assert "ANTHROPIC_API_KEY=\n" in (root / ".env.example").read_text(encoding="utf-8")
    assert ".env" in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
