"""Deterministic mock LLM for automated tests and offline demos. It never contacts any API.

``MockProvider`` replays scripted turns. ``investigation_script`` builds a ready-made plan
for "Investigate <system>" whose final summary is composed *from the tool results the
provider actually received* (it knows no numbers of its own), so it exercises the same
grounding rules a live model must follow.
"""

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from risksignal.agent.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    ToolCall,
    ToolSpec,
)

Step = LLMResponse | Callable[[list[LLMMessage]], LLMResponse]


class MockProvider(LLMProvider):
    """Returns scripted responses in order. Records every request in ``calls`` for assertions."""

    name = "mock"

    def __init__(self, steps: Sequence[Step]) -> None:
        self._steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self, system: str, messages: list[LLMMessage], tools: list[ToolSpec], max_tokens: int
    ) -> LLMResponse:
        index = len(self.calls)
        self.calls.append({"system": system, "messages": list(messages),
                           "tool_names": [t.name for t in tools], "max_tokens": max_tokens})
        if index >= len(self._steps):
            raise LLMProviderError("The mock provider has no more scripted responses.")
        step = self._steps[index]
        return step(messages) if callable(step) else step


def tool_request(call_id: str, name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


def results_by_tool(messages: list[LLMMessage]) -> dict[str, dict[str, Any]]:
    """Parsed JSON tool results found in a conversation, keyed by tool name."""
    names: dict[str, str] = {}
    found: dict[str, dict[str, Any]] = {}
    for message in messages:
        for call in message.tool_calls:
            names[call.id] = call.name
        for result in message.tool_results:
            found[names.get(result.tool_call_id, result.tool_call_id)] = json.loads(result.content)
    return found


# --------------------------------------------------------------------------- summary writing


def _money(value: float) -> str:
    return f"{value:,.0f}"


def _observed_lines(results: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    if profile := results.get("get_system_profile"):
        s, p = profile["system"], profile["primary_process"]
        lines.append(f"{s['name']} ({s['system_id']}): criticality {s['criticality']}, primary process {p['name']}.")
    if incidents := results.get("get_recent_incidents"):
        c = incidents["counts"]
        categories = ", ".join(f"{k}: {v}" for k, v in c["by_category"].items()) or "none"
        lines.append(f"{c['total']} incidents in the last {incidents['months']} months ({categories}); "
                     f"{c['deployment_keyword_matches']} descriptions mention deployment; "
                     f"total recorded loss {_money(c['total_financial_loss'])}.")
    if kris := results.get("get_kri_history"):
        for series in kris["series"]:
            change = series["change_vs_previous_window_percent"]
            text = f", {change:.1f}% vs the previous window" if change is not None else ""
            lines.append(f"KRI {series['kri_name']}: latest {series['latest_value']:.2f}, "
                         f"window mean {series['window_mean']:.2f}{text}.")
    if controls := results.get("get_controls"):
        lines.append(f"{len(controls['controls'])} controls; overdue reviews: "
                     f"{', '.join(controls['overdue_control_ids']) or 'none'}; "
                     f"due: {', '.join(controls['due_control_ids']) or 'none'}.")
    return lines


def _assumption_lines(results: dict[str, dict[str, Any]]) -> list[str]:
    simulation = results.get("run_loss_simulation") or results.get("compare_baseline_and_stress")
    if not simulation:
        return []
    basis = simulation["observed_basis"]
    a = simulation.get("model_assumptions") or simulation["baseline_assumptions"]
    lines = [
        f"Frequency: Poisson, lambda {a['lambda_used']:.2f} per year, source {a['lambda_source']} "
        f"({basis['observed_incident_count']} observed incidents over {basis['observation_years']:.2f} years).",
        f"Severity: Lognormal, mu {a['severity_mu']:.3f}, sigma {a['severity_sigma']:.3f}, fitted to "
        f"{basis['severity_losses_used']} losses (data source {basis['severity_data_source']}).",
        f"{a['number_of_simulations']:,} simulated years, seed {a['random_seed']}. Parameters are illustrative.",
    ]
    if stress := results.get("compare_baseline_and_stress"):
        scenario = stress["stress_assumptions"]["scenario"]
        lines.append(f"Stress scenario {scenario['scenario_id']}: illustrative assumptions, not calibrated.")
    return lines


def _simulation_lines(results: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    if simulation := results.get("run_loss_simulation"):
        m = simulation["simulation_results"]["metrics"]
        lines.append(f"Baseline annual loss: mean {_money(m['mean'])}, median {_money(m['median'])}, "
                     f"P95 {_money(m['p95'])}, P99 {_money(m['p99'])}, "
                     f"ES95 {_money(m['expected_shortfall_95'])}, ES99 {_money(m['expected_shortfall_99'])}.")
    if stress := results.get("compare_baseline_and_stress"):
        out = stress["simulation_results"]
        b, s, pct = out["baseline_metrics"], out["stress_metrics"], out["percentage_differences"]
        lines.append(f"Stress scenario: P95 {_money(b['p95'])} (baseline) vs {_money(s['p95'])} (stress), "
                     f"a difference of {pct['p95']:.1f}%; ES95 {_money(s['expected_shortfall_95'])} under stress.")
    return lines


def _exposure_lines(results: dict[str, dict[str, Any]]) -> list[str]:
    deps = results.get("get_dependencies")
    if not deps:
        return []
    lines = [f"Vendors: {', '.join(v['name'] + ' (' + v['vendor_id'] + ')' for v in deps['vendors']) or 'none'}."]
    for shared in deps["shared_vendors"]:
        others = ", ".join(o["system_id"] for o in shared["other_systems"])
        lines.append(f"{shared['vendor']['name']} ({shared['vendor']['vendor_id']}) is also used by {others}.")
    return lines


def _question_lines(results: dict[str, dict[str, Any]]) -> list[str]:
    questions: list[str] = []
    if (incidents := results.get("get_recent_incidents")) and incidents["counts"]["deployment_keyword_matches"]:
        questions.append("Has deployment governance changed? Which releases were involved in the incidents?")
    if controls := results.get("get_controls"):
        for control in controls["controls"]:
            if control["review_status"] == "overdue":
                questions.append(f"Should control {control['control_id']} ({control['name']}) be retested?")
    if deps := results.get("get_dependencies"):
        for shared in deps["shared_vendors"]:
            for other in shared["other_systems"]:
                questions.append(f"Does {shared['vendor']['name']} create concentration risk, and does "
                                 f"{other['system_id']} have similar exposure?")
    return questions or ["Which additional evidence would an analyst want before drawing conclusions?"]


def compose_summary(results: dict[str, dict[str, Any]]) -> str:
    """Write the sectioned investigation summary using only values found in ``results``."""
    sections = [
        ("Observed evidence", _observed_lines(results)),
        ("Model assumptions", _assumption_lines(results)),
        ("Simulation results", _simulation_lines(results)),
        ("Connected exposures", _exposure_lines(results)),
        ("Suggested investigation questions", _question_lines(results)),
        ("Limitations", ["All data are synthetic (fictional Atlas Bank) and the model is illustrative. "
                         "Simulation results are outputs under stated assumptions, not forecasts."]),
    ]
    return "\n\n".join(f"{title}\n" + "\n".join(f"- {line}" for line in lines)
                       for title, lines in sections if lines)


def _failure_summary(results: dict[str, dict[str, Any]]) -> str:
    errors = [r for r in results.values() if r.get("ok") is False]
    lines = [f"{e['tool_name']}: {e['message']}" for e in errors]
    suggestions = sorted({s for e in errors for s in e.get("suggestions", [])})
    text = "I could not complete the investigation.\n" + "\n".join(f"- {line}" for line in lines)
    if suggestions:
        text += f"\nPossible matches: {', '.join(suggestions)}. Please tell me which system you meant."
    return text


# --------------------------------------------------------------------------- ready-made plan


def investigation_script(system_id: str, include_stress: bool = False) -> MockProvider:
    """A scripted provider that investigates ``system_id`` like a careful analyst would.

    Turn 1 asks for the system profile. Turn 2 either stops (if the profile failed) or asks for
    the remaining tools in one batch. Turn 3 writes the summary from the results it was given.
    """

    def second_turn(messages: list[LLMMessage]) -> LLMResponse:
        if results_by_tool(messages).get("get_system_profile", {}).get("ok") is False:
            return LLMResponse(text=_failure_summary(results_by_tool(messages)))
        calls = [
            tool_request("c2", "get_recent_incidents", system_id=system_id, months=12),
            tool_request("c3", "get_kri_history", system_id=system_id, months=12),
            tool_request("c4", "get_controls", system_id=system_id),
            tool_request("c5", "get_dependencies", system_id=system_id),
            tool_request("c6", "run_loss_simulation", system_id=system_id,
                         number_of_simulations=100_000, random_seed=42),
        ]
        if include_stress:
            calls.append(tool_request("c7", "compare_baseline_and_stress", system_id=system_id,
                                      scenario_id="SHARED_VENDOR_OUTAGE",
                                      number_of_simulations=100_000, random_seed=42))
        return LLMResponse(tool_calls=calls, stop_reason="tool_use")

    def third_turn(messages: list[LLMMessage]) -> LLMResponse:
        results = results_by_tool(messages)
        if any(r.get("ok") is False for r in results.values()):
            return LLMResponse(text=_failure_summary(results) + "\n\n" + compose_summary(
                {k: v for k, v in results.items() if v.get("ok") is not False}))
        return LLMResponse(text=compose_summary(results))

    first = LLMResponse(tool_calls=[tool_request("c1", "get_system_profile", system_id=system_id)],
                        stop_reason="tool_use")
    return MockProvider([first, second_turn, third_turn])


_SYSTEM_ID = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_STRESS_WORDS = re.compile(r"\b(stress(?:ed)?|scenario|vendor outage|what[- ]if)\b", re.IGNORECASE)


def provider_for_question(question: str, include_stress: bool | None = None) -> MockProvider:
    """A mock provider for a free-text question, for offline use (CLI, API mock mode).

    The system is the first identifier in the text that looks like ``PAYMENT_ENGINE_01``. If
    there is none, the provider asks the user to name one instead of guessing. The stress
    comparison is included when asked for, or when the question mentions stress, a scenario,
    a vendor outage or a what-if.
    """
    match = _SYSTEM_ID.search(question)
    if match is None:
        return MockProvider([LLMResponse(
            text="Please name the system to investigate, for example PAYMENT_ENGINE_01.")])
    stress = _STRESS_WORDS.search(question) is not None if include_stress is None else include_stress
    return investigation_script(match.group(0), include_stress=stress)
