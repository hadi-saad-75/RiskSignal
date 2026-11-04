"""Tests for the conversational assistant: portfolio tool, chat registry, offline assistant, API and page.
No test contacts the Anthropic API."""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from risksignal.agent.assistant import Assistant, history_messages
from risksignal.agent.base import LLMResponse
from risksignal.agent.investigator import find_ungrounded_numbers, remove_long_dashes
from risksignal.agent.mock_assistant import CAPABILITIES, assistant_provider
from risksignal.agent.mock_provider import MockProvider
from risksignal.agent.prompts import CHAT_SYSTEM_PROMPT, GROUND_RULES, SYSTEM_PROMPT
from risksignal.agent.schemas import ChatTurn
from risksignal.agent.tool_registry import build_chat_registry, build_default_registry
from risksignal.api.dependencies import Settings, get_settings, get_tool_context
from risksignal.api.main import create_app
from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.tools.context import ToolContext
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.system_tools import get_portfolio_summary
from risksignal.ui.api_client import ApiClient

FOCAL = "PAYMENT_ENGINE_01"
PORTFOLIO_TOOLS = {"list_systems", "get_portfolio_summary", "get_bank_overview", "list_scenarios"}


@pytest.fixture(scope="module")
def ctx(tmp_path_factory: pytest.TempPathFactory) -> ToolContext:
    return ToolContext(db_path=save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("assistant_db")))


@pytest.fixture(scope="module")
def http(ctx: ToolContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_tool_context] = lambda: ctx
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=ctx.db_path, llm_provider="mock")
    return TestClient(app)


def converse(ctx: ToolContext, *questions: str) -> list[Any]:
    """Run a whole conversation through the offline assistant, as the API would."""
    registry, history, results = build_chat_registry(ctx), [], []
    for question in questions:
        provider = assistant_provider(question, [t.content for t in history])
        result = Assistant(provider, registry).reply(question, history)
        history += [ChatTurn(role="user", content=question), ChatTurn(role="assistant", content=result.final_answer)]
        results.append(result)
    return results


def tools_of(result: Any) -> list[str]:
    return [a.tool_name for a in result.tool_activity]


# ----------------------------------------------------------------- portfolio tool


def test_portfolio_summary_agrees_with_the_per_system_tool(ctx: ToolContext) -> None:
    summary = get_portfolio_summary(ctx, 12)
    assert summary.ok and summary.totals.systems == len(summary.systems) == 20
    losses = [s.recorded_loss for s in summary.systems]
    assert losses == sorted(losses, reverse=True)
    for system in summary.systems:
        incidents = get_recent_incidents(ctx, system.system_id, 12)
        assert system.incidents == incidents.counts.total
        assert system.recorded_loss == pytest.approx(incidents.counts.total_financial_loss)
        assert system.incident_change == system.incidents - system.incidents_previous_window
    assert summary.totals.incidents == sum(s.incidents for s in summary.systems)
    assert summary.totals.systems_with_overdue_controls == sorted(
        s.system_id for s in summary.systems if s.overdue_controls)


def test_portfolio_summary_rejects_bad_windows(ctx: ToolContext) -> None:
    for months in (0, 121, "12", True):
        result = get_portfolio_summary(ctx, months)  # type: ignore[arg-type]
        assert not result.ok and result.error_type == "invalid_argument"


# ----------------------------------------------------------------- registry and prompts


def test_chat_registry_adds_bank_wide_tools_and_leaves_the_investigation_registry_alone(ctx: ToolContext) -> None:
    chat, default = set(build_chat_registry(ctx).names), set(build_default_registry(ctx).names)
    assert len(default) == 7 and chat == default | PORTFOLIO_TOOLS
    assert "compare_baseline_and_custom_scenario" not in chat  # user-supplied assumptions stay out of the agent


def test_both_prompts_share_the_ground_rules_and_contain_no_figures() -> None:
    assert GROUND_RULES in SYSTEM_PROMPT and GROUND_RULES in CHAT_SYSTEM_PROMPT
    assert "get_portfolio_summary" in CHAT_SYSTEM_PROMPT and "long dashes" in CHAT_SYSTEM_PROMPT
    assert not re.search(r"\d{3,}", CHAT_SYSTEM_PROMPT)  # no example figures, identifiers only
    assert not re.search(r"\d\s*(thousand|million|billion|k\b|m\b|%)", CHAT_SYSTEM_PROMPT, re.IGNORECASE)


# ----------------------------------------------------------------- house style and grounding


@pytest.mark.parametrize("raw, clean", [
    ("Loss rose \u2014 sharply.", "Loss rose, sharply."),
    ("from 2021\u20132026", "from 2021 to 2026"),
    ("frequency\u2013severity model", "frequency-severity model"),
    ("\u2014 first point", "- first point"),
    ("this\u2014and that", "this, and that"),
])
def test_long_dashes_are_removed(raw: str, clean: str) -> None:
    assert remove_long_dashes(raw) == clean


def test_long_dashes_never_reach_the_user(ctx: ToolContext) -> None:
    provider = MockProvider([LLMResponse(text="Observed evidence \u2014 nothing unusual \u2013 see 2021\u20132022.")])
    answer = Assistant(provider, build_chat_registry(ctx)).reply("Anything unusual?").final_answer
    assert "\u2014" not in answer and "\u2013" not in answer


def test_numbers_from_earlier_turns_count_as_grounded() -> None:
    assert find_ungrounded_numbers("P95 was 896,435.", []) == ["896,435"]
    assert find_ungrounded_numbers("P95 was 896,435.", [], context=["Earlier: P95 896,435"]) == []


def test_history_always_alternates_and_ends_with_the_assistant() -> None:
    turns = [ChatTurn(role="assistant", content="stray"), ChatTurn(role="user", content="a"),
             ChatTurn(role="user", content="b"), ChatTurn(role="assistant", content="c"),
             ChatTurn(role="assistant", content="  "), ChatTurn(role="user", content="unanswered")]
    messages = history_messages(turns)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].text == "a\n\nb" and messages[1].text == "c"


# ----------------------------------------------------------------- offline assistant behaviour


def test_the_assistant_adapts_to_each_kind_of_question(ctx: ToolContext) -> None:
    greeting, portfolio, incidents, follow_up, concept, latest = converse(
        ctx,
        "Hello, what can you do?",
        "Which systems should I look at first?",
        f"What incidents did {FOCAL} have?",
        "And are its controls up to date?",
        "What is Expected Shortfall?",
        "What are the latest incidents?",
    )
    assert greeting.final_answer == CAPABILITIES and tools_of(greeting) == []
    assert tools_of(portfolio) == ["get_portfolio_summary"] and "| System |" in portfolio.final_answer
    assert tools_of(incidents) == ["get_recent_incidents"] and FOCAL in incidents.final_answer
    assert tools_of(follow_up) == ["get_controls"] and follow_up.tool_activity[0].tool_input["system_id"] == FOCAL
    assert tools_of(concept) == [] and "Expected Shortfall" in concept.final_answer
    assert tools_of(latest) == ["get_bank_overview"]
    for result in (greeting, portfolio, incidents, follow_up, concept, latest):
        assert result.status == "completed" and result.ungrounded_numbers == [] and result.warnings == []


def test_a_broad_request_runs_the_full_investigation(ctx: ToolContext) -> None:
    (result,) = converse(ctx, f"Investigate {FOCAL} under the shared vendor outage scenario.")
    assert {"get_system_profile", "get_controls", "compare_baseline_and_stress"} <= set(tools_of(result))
    assert "Suggested investigation questions" in result.final_answer and result.ungrounded_numbers == []


def test_a_follow_up_without_any_system_asks_which_one(ctx: ToolContext) -> None:
    (result,) = converse(ctx, "Are the controls up to date?")
    assert tools_of(result) == [] and "Which system" in result.final_answer


def test_an_unknown_system_is_reported_with_suggestions(ctx: ToolContext) -> None:
    (result,) = converse(ctx, "What incidents did PAYMENT_ENGINE_09 have?")
    assert result.tool_activity[0].status == "failed" and "PAYMENT_ENGINE_01" in result.final_answer


# ----------------------------------------------------------------- API


def test_chat_endpoint_answers_with_history(http: TestClient) -> None:
    first = http.post("/agent/chat", json={"message": f"What incidents did {FOCAL} have?"})
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "completed" and body["activity_log"] and FOCAL in body["final_response"]
    assert body["tool_activity"][0]["output"] is None  # outputs only on request

    second = http.post("/agent/chat", json={
        "message": "Who are its vendors?", "include_tool_outputs": True,
        "history": [{"role": "user", "content": f"What incidents did {FOCAL} have?"},
                    {"role": "assistant", "content": body["final_response"]}],
    })
    assert second.status_code == 200
    activity = second.json()["tool_activity"]
    assert activity[0]["tool_name"] == "get_dependencies" and activity[0]["tool_input"]["system_id"] == FOCAL
    assert activity[0]["output"] is not None


@pytest.mark.parametrize("payload", [
    {"message": ""},
    {"message": "   "},
    {"message": "hi", "history": [{"role": "system", "content": "x"}]},
    {"message": "hi", "unexpected": True},
])
def test_chat_endpoint_rejects_invalid_requests(http: TestClient, payload: dict[str, Any]) -> None:
    response = http.post("/agent/chat", json=payload)
    assert response.status_code == 422 and "error" in response.json()


# ----------------------------------------------------------------- dashboard page


def test_assistant_page_holds_a_conversation(http: TestClient) -> None:
    at = AppTest.from_string("from risksignal.ui.views.assistant import render_assistant\nrender_assistant()",
                             default_timeout=60)
    at.session_state["api_client"] = ApiClient(base_url="http://testserver", client=http)
    at.run()
    assert not at.exception and at.title[0].value == "Ask RiskSignal"
    assert any("Which systems should I look at first?" == b.label for b in at.button)

    at.chat_input[0].set_value(f"What incidents did {FOCAL} have?").run()
    assert not at.exception
    shown = " | ".join(m.value for m in at.markdown)
    assert FOCAL in shown and "incidents" in shown
    assert any(e.label.startswith("Evidence") for e in at.expander)

    at.chat_input[0].set_value("And its controls?").run()
    assert not at.exception and "controls" in " | ".join(m.value for m in at.markdown)
    assert len(at.session_state["assistant_history"]) == 4

    next(b for b in at.button if b.label == "Start a new conversation").click().run()
    assert not at.exception and at.session_state["assistant_history"] == []


def test_assistant_page_starter_question_runs(http: TestClient) -> None:
    at = AppTest.from_string("from risksignal.ui.views.assistant import render_assistant\nrender_assistant()",
                             default_timeout=60)
    at.session_state["api_client"] = ApiClient(base_url="http://testserver", client=http)
    at.run()
    next(b for b in at.button if b.label == "Which systems should I look at first?").click().run()
    assert not at.exception
    assert at.session_state["assistant_history"][1]["activity"] == ["Compared all 20 systems over 12 months"]
