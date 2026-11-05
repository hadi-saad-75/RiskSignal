"""Deterministic offline stand-in for the conversational assistant. It never contacts any API.

It recognises the common kinds of operator question by keywords, asks the real tools for the
data, and writes the answer only from the tool results it receives (it knows no numbers of its
own), so offline demos and tests exercise the same grounding rules as a live model. It is far
less flexible than a language model: questions it does not recognise get a short guide to what
it can answer.
"""

import re
from collections.abc import Callable, Sequence
from typing import Any

from risksignal.agent.base import LLMMessage, LLMResponse, ToolCall
from risksignal.agent.mock_provider import (
    MockProvider,
    _assumption_lines,
    _exposure_lines,
    _failure_summary,
    _money,
    _observed_lines,
    _simulation_lines,
    investigation_script,
    results_by_tool,
    tool_request,
)
from risksignal.stochastic.scenario import PREDEFINED_SCENARIOS

DEFAULT_SCENARIO = "SHARED_VENDOR_OUTAGE"
SYNTHETIC_NOTE = "_Synthetic Atlas Bank data._"
MODEL_NOTE = "_Model outputs under illustrative assumptions fitted to synthetic data, not forecasts._"

_SYSTEM_ID = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*_\d+\b")
_MONTHS = re.compile(r"\b(\d{1,3})\s*months?\b", re.IGNORECASE)

_GREETING = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|help)\b|what can you do|how can you help"
                       r"|who are you|how do you work", re.IGNORECASE)
_CONCEPT = re.compile(r"\b(what is|what's|what are|what does|explain|meaning|define|definition|difference between"
                      r"|how (is|are|does|do))\b", re.IGNORECASE)
_PORTFOLIO = re.compile(r"\b(which systems?|what systems?|all (the )?systems|across|portfolio|bank[- ]wide|whole bank"
                        r"|look first|focus on|prioriti[sz]e|stand out|attention|most|highest|worst|top \d*|rank"
                        r"|compare (the )?systems)\b", re.IGNORECASE)
_LIST_SYSTEMS = re.compile(r"\b(list|show)( me)? (all )?(the )?systems\b|systems (are there|exist|do you (have|know))"
                           r"|how many systems", re.IGNORECASE)
_BANK_RECENT = re.compile(r"\b(latest|recent|last|newest)\b.*\bincidents?\b|\bincidents?\b.*\b(latest|recent)\b",
                          re.IGNORECASE)
_LIST_SCENARIOS = re.compile(r"\bscenarios?\b", re.IGNORECASE)

_SYSTEM_INTENTS: dict[str, re.Pattern[str]] = {
    "stress": re.compile(r"stress|scenario|vendor outage|what[- ]if|shock", re.IGNORECASE),
    "incidents": re.compile(r"incident|happened|events?\b|recorded loss", re.IGNORECASE),
    "kri": re.compile(r"\bkris?\b|indicator|downtime|near[- ]miss|deployment rate|exception", re.IGNORECASE),
    "controls": re.compile(r"control|review|overdue|retest", re.IGNORECASE),
    "dependencies": re.compile(r"vendor|depend|related|connected|exposure|shared|upstream|downstream|third[- ]party",
                               re.IGNORECASE),
    "simulation": re.compile(r"simulat|\bp9[59]\b|\bvar\b|value at risk|expected shortfall|\bes9[59]\b|tail"
                             r"|annual loss|loss distribution|monte carlo|how much could", re.IGNORECASE),
    "profile": re.compile(r"profile|describe|criticality|what is [a-z_]+_\d+|business process", re.IGNORECASE),
}
_FULL = re.compile(r"investigat|assess|deep dive|analy[sz]e|full picture|everything|overview of|summary of"
                   r"|tell me about|how is [a-z_]+_\d+ doing", re.IGNORECASE)

GLOSSARY: dict[str, tuple[re.Pattern[str], str]] = {
    "currency": (re.compile(r"currency|dollars?|\busd\b|euros?|\beur\b|monetary units", re.IGNORECASE),
        "Losses are in **synthetic monetary units**. Atlas Bank has no currency field, so the amounts are "
        "not specified as dollars, euros or any other real currency. Historical and simulated losses use "
        "the same units. Real use would require an agreed currency and loss definition."),
    "expected_shortfall": (re.compile(r"expected shortfall|\bes9[59]?\b|\bcvar\b", re.IGNORECASE),
        "**Expected Shortfall** answers the question: when a bad year happens, how bad is it on average? "
        "ES95 is the average annual loss across the worst one-in-twenty simulated years, so it always sits at "
        "or above P95. It looks inside the tail instead of only marking where the tail starts."),
    "percentile": (re.compile(r"\bp9[59]\b|percentile|\bvar\b|value at risk", re.IGNORECASE),
        "**P95 and P99** (Value at Risk style percentiles) are thresholds of the simulated annual loss. P95 is "
        "the loss that is exceeded in one simulated year out of twenty; P99 the loss exceeded in one year out "
        "of a hundred. They say where the tail begins, not how deep it goes."),
    "kri": (re.compile(r"\bkris?\b|key risk indicator", re.IGNORECASE),
        "A **Key Risk Indicator (KRI)** is a measured signal that may move before losses do, such as failed "
        "deployment rate, downtime minutes, near misses, control exceptions or vendor incidents. RiskSignal "
        "shows each KRI against its window mean and its change on the previous window; it does not project them."),
    "frequency": (re.compile(r"poisson|frequency|lambda|\u03bb", re.IGNORECASE),
        "**Frequency** is modelled with a **Poisson** distribution: the number of incidents in a year is "
        "random with mean **lambda**. Lambda is estimated as the observed incident count divided by the "
        "observation period in years, with a bank-wide fallback when a system has too few incidents."),
    "severity": (re.compile(r"lognormal|severity|\bmu\b|\bsigma\b|\u03bc|\u03c3", re.IGNORECASE),
        "**Severity**, the loss of a single incident, follows a **Lognormal** distribution: its logarithm is "
        "bell shaped with mean **mu** and spread **sigma**. exp(mu) is the median loss of one incident, and a "
        "larger sigma means a heavier tail of rare, very large losses."),
    "monte_carlo": (re.compile(r"monte carlo|simulation|aggregate loss", re.IGNORECASE),
        "The **Monte Carlo simulation** draws many synthetic years. In each year it draws a number of "
        "incidents from the Poisson model and a loss for each from the Lognormal model, and adds them up. The "
        "spread of those annual totals gives the mean, median, percentiles and Expected Shortfall."),
    "stress": (re.compile(r"stress|scenario", re.IGNORECASE),
        "A **stress scenario** applies explicit, illustrative changes to the baseline model, for example "
        "more frequent incidents or heavier losses after a shared vendor outage, and compares the result with "
        "the baseline using the same random numbers. The scenario numbers are assumptions, not calibrated."),
    "control": (re.compile(r"\bcontrols?\b|overdue|review status", re.IGNORECASE),
        "A **control** is a safeguard such as a pre-release test or a reconciliation. Its review status is "
        "current, due or overdue. An overdue review is a reason to ask questions, not proof that the control "
        "has failed."),
    "operational_risk": (re.compile(r"operational risk|op risk", re.IGNORECASE),
        "**Operational Risk** is the risk of loss from failed processes, people or systems, or from external "
        "events. RiskSignal focuses on technology: outages, failed deployments, vendor failures, human error "
        "and cyber events."),
}

CAPABILITIES = (
    "I can help you look into the Atlas Bank technology systems using read-only tools. For example:\n\n"
    "- **Across the portfolio:** \"Which systems should I look at first?\" or \"What are the latest incidents?\"\n"
    "- **One system:** \"What incidents did PAYMENT_ENGINE_01 have?\", \"Are its controls up to date?\", "
    "\"Who are its vendors?\"\n"
    "- **Loss modelling:** \"What is the P95 annual loss for CORE_LEDGER_01?\" or \"What happens under a shared "
    "vendor outage?\"\n"
    "- **Methods:** \"What is Expected Shortfall?\" or \"How is lambda estimated?\"\n\n"
    "Every figure comes from the tools, and the data are synthetic."
)


# --------------------------------------------------------------------------- reading the question


def _system_in(text: str) -> str | None:
    for match in _SYSTEM_ID.finditer(text):
        candidate = match.group(0).upper()
        if candidate not in PREDEFINED_SCENARIOS:
            return candidate
    return None


def _scenario_in(text: str) -> str | None:
    upper = text.upper()
    return next((s for s in sorted(PREDEFINED_SCENARIOS) if s in upper), None)


def _months_in(text: str, default: int = 12) -> int:
    if match := _MONTHS.search(text):
        return max(1, min(120, int(match.group(1))))
    if re.search(r"\bquarter\b", text, re.IGNORECASE):
        return 3
    if re.search(r"\btwo years\b|\b2 years\b", text, re.IGNORECASE):
        return 24
    return default


def _last_system(history: Sequence[str]) -> str | None:
    for text in reversed(history):
        if system := _system_in(text):
            return system
    return None


# --------------------------------------------------------------------------- writing answers


def _incidents_answer(r: dict[str, Any]) -> str:
    c = r["counts"]
    lines = [f"**{r['system_id']}** had **{c['total']} incidents** in the last {r['months']} months, with a total "
             f"recorded loss of {_money(c['total_financial_loss'])}."]
    lines += [f"- {i['date']} · {i['incident_id']} · {i['category'].replace('_', ' ')}, {i['severity']} severity, "
              f"loss {_money(i['financial_loss'])}: {i['description']}" for i in r["incidents"]]
    if c["deployment_keyword_matches"]:
        lines.append(f"\n{c['deployment_keyword_matches']} descriptions mention deployment (a keyword match; the "
                     "data have no separate cause field).")
    return "\n".join(lines)


def _controls_answer(r: dict[str, Any]) -> str:
    overdue, due = r["overdue_control_ids"], r["due_control_ids"]
    head = f"**{r['system_id']}** has {len(r['controls'])} controls. "
    head += f"Overdue reviews: **{', '.join(overdue)}**. " if overdue else "No review is overdue. "
    head += f"Due: {', '.join(due)}." if due else ""
    lines = [head.strip()]
    lines += [f"- {c['control_id']} {c['name']} ({c['control_type']}): {c['review_status']}, last reviewed "
              f"{c['last_review_date']} ({c['days_since_last_review']} days ago)" for c in r["controls"]]
    if overdue:
        lines.append("\nAn overdue review is a reason to ask questions, not proof that a control has failed.")
    return "\n".join(lines)


def _dependencies_answer(r: dict[str, Any]) -> str:
    lines = [f"- {line}" for line in _exposure_lines({"get_dependencies": r})]
    related = [f"{x['system']['system_id']} ({' '.join(rel['explanation'] for rel in x['relationships'])})"
               for x in r["related_systems"]]
    if related:
        lines.append(f"- Related systems: {'; '.join(related)}")
    lines.append("\nSharing a vendor or process is a shared exposure worth investigating, not evidence that a "
                 "failure in one system causes a failure in another.")
    return "\n".join(lines)


def _section_text(kind: str, results: dict[str, dict[str, Any]]) -> str:
    if kind == "incidents":
        return _incidents_answer(results["get_recent_incidents"])
    if kind == "controls":
        return _controls_answer(results["get_controls"])
    if kind == "dependencies":
        return _dependencies_answer(results["get_dependencies"])
    if kind == "kri":
        kri = results["get_kri_history"]
        head = f"Key risk indicators for **{kri['system_id']}** over the last {kri['months']} months:\n"
        return head + "\n".join(f"- {line}" for line in _observed_lines({"get_kri_history": kri}))
    if kind == "profile":
        profile = results["get_system_profile"]
        return " ".join(_observed_lines({"get_system_profile": profile})) + f" {profile['system']['description']}"
    lines = _simulation_lines(results) + _assumption_lines(results)
    return "\n".join(f"- {line}" for line in lines) + f"\n\n{MODEL_NOTE}"


_TITLES = {"profile": "Profile", "incidents": "Incidents", "kri": "Key risk indicators", "controls": "Controls",
           "dependencies": "Vendors and connected systems", "simulation": "Loss simulation",
           "stress": "Stress comparison"}
_TOOL_FOR = {"profile": "get_system_profile", "incidents": "get_recent_incidents", "kri": "get_kri_history",
             "controls": "get_controls", "dependencies": "get_dependencies", "simulation": "run_loss_simulation",
             "stress": "compare_baseline_and_stress"}
_NEXT = {"incidents": "Are its controls up to date?", "controls": "What does the loss simulation show?",
         "kri": "Which incidents explain these movements?", "dependencies": "What happens under a shared vendor outage?",
         "simulation": "How does this change under a stress scenario?", "stress": "Which vendors are shared?",
         "profile": "What incidents did it have recently?"}


def _system_turns(system_id: str, kinds: list[str], months: int, scenario: str) -> list[Any]:
    calls: list[ToolCall] = []
    for number, kind in enumerate(kinds, start=1):
        arguments: dict[str, Any] = {"system_id": system_id}
        if kind in ("incidents", "kri"):
            arguments["months"] = months
        if kind == "stress":
            arguments["scenario_id"] = scenario
        calls.append(ToolCall(id=f"a{number}", name=_TOOL_FOR[kind], arguments=arguments))

    def answer(messages: list[LLMMessage]) -> LLMResponse:
        results = results_by_tool(messages)
        if any(r.get("ok") is False for r in results.values()):
            return LLMResponse(text=_failure_summary(results))
        if len(kinds) == 1:
            body = _section_text(kinds[0], results)
        else:
            body = "\n\n".join(f"**{_TITLES[k]}**\n\n{_section_text(k, results)}" for k in kinds)
        notes = "" if "simulation" in kinds or "stress" in kinds else f"\n\n{SYNTHETIC_NOTE}"
        return LLMResponse(text=f"{body}{notes}\n\nYou could ask next: {_NEXT[kinds[-1]]}")

    return [LLMResponse(tool_calls=calls, stop_reason="tool_use"), answer]


def _portfolio_answer(r: dict[str, Any]) -> str:
    systems, totals = r["systems"], r["totals"]
    lines = [f"Over the last {r['months']} months (to {r['window_end_inclusive']}), the {totals['systems']} systems "
             f"recorded {totals['incidents']} incidents and a total loss of {_money(totals['recorded_loss'])}. "
             "Sorted by recorded loss, these stand out:", "",
             "| System | Criticality | Incidents | High or critical | Recorded loss | Change vs previous window "
             "| Overdue controls |", "|---|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {s['system_id']} | {s['criticality']} | {s['incidents']} | {s['high_or_critical_incidents']} | "
              f"{_money(s['recorded_loss'])} | {s['incident_change']:+d} | {s['overdue_controls']} |".replace("| +0 |", "| 0 |")
              for s in systems[:5]]
    rising = max(systems, key=lambda s: (s["incident_change"], s["recorded_loss"]))
    lines.append("")
    if rising["incident_change"] > 0:
        lines.append(f"- Largest rise in incident count against the previous window: **{rising['system_id']}** "
                     f"({rising['incident_change']:+d}).")
    if totals["systems_with_overdue_controls"]:
        lines.append(f"- Systems with overdue control reviews: {', '.join(totals['systems_with_overdue_controls'])}.")
    lines.append("\nThese are observable synthetic facts to help decide where to look, not a risk rating.")
    lines.append(f"\nYou could ask next: Investigate {systems[0]['system_id']}.")
    return "\n".join(lines)


def _bank_recent_answer(r: dict[str, Any]) -> str:
    lines = [f"The {len(r['recent_incidents'])} most recent incidents across the bank:"]
    lines += [f"- {i['date']} · **{i['system_id']}** · {i['incident_id']} · {i['category'].replace('_', ' ')}, "
              f"{i['severity']} severity, loss {_money(i['financial_loss'])}: {i['description']}"
              for i in r["recent_incidents"]]
    return "\n".join(lines) + f"\n\n{SYNTHETIC_NOTE}"


def _systems_answer(r: dict[str, Any]) -> str:
    lines = [f"There are {len(r['systems'])} systems in scope:", "", "| System | Name | Criticality | Primary process |",
             "|---|---|---|---|"]
    lines += [f"| {s['system_id']} | {s['name']} | {s['criticality']} | {s['primary_process_name']} |"
              for s in r["systems"]]
    return "\n".join(lines)


def _scenarios_answer(r: dict[str, Any]) -> str:
    lines = ["The predefined stress scenarios (illustrative assumptions, not calibrated):"]
    lines += [f"- **{s['name']}** ({s['scenario_id']}): frequency x{s['lambda_multiplier']:g}, log-severity "
              f"shift {s['severity_mu_shift']:g}, spread x{s['severity_sigma_multiplier']:g}. {s['description']}"
              for s in r["scenarios"]]
    return "\n".join(lines)


def _one_tool(name: str, arguments: dict[str, Any], write: Callable[[dict[str, Any]], str]) -> MockProvider:
    def answer(messages: list[LLMMessage]) -> LLMResponse:
        result = results_by_tool(messages)[name]
        return LLMResponse(text=_failure_summary({name: result}) if result.get("ok") is False else write(result))

    return MockProvider([LLMResponse(tool_calls=[tool_request("p1", name, **arguments)], stop_reason="tool_use"),
                         answer])


def _glossary_answer(text: str) -> str | None:
    entries = [body for pattern, body in GLOSSARY.values() if pattern.search(text)]
    return "\n\n".join(entries[:2]) if entries else None


# --------------------------------------------------------------------------- entry point


def assistant_provider(message: str, history: Sequence[str] = ()) -> MockProvider:
    """A scripted provider that answers ``message`` in the context of earlier turns ``history``."""
    system = _system_in(message)
    months = _months_in(message)
    portfolio = bool(_PORTFOLIO.search(message) or _LIST_SYSTEMS.search(message))
    kinds = [kind for kind, pattern in _SYSTEM_INTENTS.items() if pattern.search(message)]

    if system is None and _CONCEPT.search(message) and not portfolio and (explained := _glossary_answer(message)):
        return MockProvider([LLMResponse(text=explained)])
    if system is None and _GREETING.search(message) and not portfolio:
        return MockProvider([LLMResponse(text=CAPABILITIES)])
    if system is None and _LIST_SYSTEMS.search(message):
        return _one_tool("list_systems", {}, _systems_answer)
    if system is None and _BANK_RECENT.search(message) and not _PORTFOLIO.search(message):
        return _one_tool("get_bank_overview", {"recent_incidents": 5}, _bank_recent_answer)
    if system is None and portfolio:
        return _one_tool("get_portfolio_summary", {"months": months}, _portfolio_answer)
    if system is None and _LIST_SCENARIOS.search(message) and not _last_system(history):
        return _one_tool("list_scenarios", {}, _scenarios_answer)
    if system is None and kinds:
        system = _last_system(history)
        if system is None:
            return MockProvider([LLMResponse(text="Which system do you mean? Give its ID, for example "
                                                  "PAYMENT_ENGINE_01, or ask me to list the systems.")])
    if system is None:
        if explained := _glossary_answer(message):
            return MockProvider([LLMResponse(text=explained)])
        return MockProvider([LLMResponse(text=CAPABILITIES)])

    if _FULL.search(message) or not kinds:
        return investigation_script(system, include_stress="stress" in kinds)
    if "stress" in kinds and "simulation" in kinds:
        kinds.remove("simulation")
    return MockProvider(_system_turns(system, kinds, months, _scenario_in(message) or DEFAULT_SCENARIO))
