"""The RiskSignal investigation agent.

The agent investigates a selected technology system by deciding which deterministic tools to
call. It is a simple loop:

    ask the model -> run the tools it requests -> give it the results -> repeat -> final answer

It has no write access, no database access and no calculator of its own: the tool registry is
its only way to read data or obtain numbers. Every tool call is recorded (name, input, status,
time, result) so an answer can be audited. The model's internal reasoning is not recorded or
exposed. Only the final answer and the tool activity are.

Live check (needs ANTHROPIC_API_KEY; sends only synthetic data to the Anthropic API):

    python -m risksignal.agent.investigator "Investigate PAYMENT_ENGINE_01."

Offline demo without any API key, using the deterministic mock provider:

    python -m risksignal.agent.investigator --mock "Investigate PAYMENT_ENGINE_01."
"""

import argparse
import datetime as dt
import re
import sys
import time
from typing import Any

from risksignal.agent.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    ToolResultBlock,
)
from risksignal.agent.prompts import SYSTEM_PROMPT
from risksignal.agent.schemas import InvestigationResult, InvestigationStatus, ToolActivity
from risksignal.agent.tool_registry import ToolRegistry, build_default_registry

DEFAULT_MAX_STEPS = 10
DEFAULT_MAX_TOKENS = 4096

# --------------------------------------------------------------------------- number grounding

_IDENTIFIER = re.compile(r"\b(?=[A-Za-z_]*\d)[A-Za-z_][A-Za-z0-9_]*\b")  # P95, V04, PAYMENT_ENGINE_01, INC0012
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*]\s*)?\d+[.)]\s")
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%|thousand|million|billion|bn|[kKmMbB])?(?!\w)"
)
_PLAIN_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SUFFIX_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}
_EXEMPT_SMALL_INTEGER = 20  # "1 in 20", "3 incidents" are explanatory, not results


def _numbers_in(value: Any, found: set[float]) -> None:
    """Collect every number appearing in a nested structure, including inside strings."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        found.add(abs(float(value)))
    elif isinstance(value, str):
        found.update(float(m) for m in _PLAIN_NUMBER.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            _numbers_in(item, found)
    elif isinstance(value, list):
        for item in value:
            _numbers_in(item, found)


def find_ungrounded_numbers(answer: str, activities: list[ToolActivity]) -> list[str]:
    """Numbers in ``answer`` that match nothing in the tool inputs or outputs.

    A best-effort safety net, not a proof. A number counts as grounded if some number the
    tools returned (or were asked with) lies within the rounding implied by how the answer
    writes it: "0.9 million" allows +/- 50,000, "896,435" allows +/- 0.5. Identifiers (P95,
    V04, PAYMENT_ENGINE_01), ISO dates, list numbering and small whole numbers are ignored.
    """
    known: set[float] = set()
    for activity in activities:
        _numbers_in(activity.tool_input, known)
        _numbers_in(activity.output, known)

    text = _LIST_MARKER.sub(" ", _ISO_DATE.sub(" ", _IDENTIFIER.sub(" ", answer)))
    ungrounded: list[str] = []
    for match in _NUMBER.finditer(text):
        whole, fraction, suffix = match.group(1), match.group(2), match.group(3)
        multiplier = _SUFFIX_MULTIPLIER.get((suffix or "").lower(), 1.0)
        value = float(whole.replace(",", "") + ("." + fraction if fraction else "")) * multiplier
        if fraction is None and suffix is None and value <= _EXEMPT_SMALL_INTEGER:
            continue
        tolerance = 0.5 * 10 ** -(len(fraction) if fraction else 0) * multiplier + 1e-9
        token = match.group(0).strip()
        if not any(abs(value - k) <= tolerance for k in known) and token not in ungrounded:
            ungrounded.append(token)
    return ungrounded


# --------------------------------------------------------------------------- the agent


class Investigator:
    """Runs one investigation: model decides, tools compute, everything is recorded."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt

    def investigate(self, question: str) -> InvestigationResult:
        """Answer ``question`` (for example "Investigate PAYMENT_ENGINE_01.") using the tools.

        Raises ``ValueError`` only for an empty question. Provider failures and step limits are
        reported in the result, never raised.
        """
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        question = question.strip()
        messages = [LLMMessage(role="user", text=question)]
        activities: list[ToolActivity] = []
        warnings: list[str] = []
        status: InvestigationStatus = "stopped_max_steps"
        final_answer = ""
        llm_calls = 0

        for _ in range(self.max_steps):
            try:
                response = self.provider.complete(
                    self.system_prompt, messages, self.registry.specs(), self.max_tokens)
            except LLMProviderError as error:
                status, final_answer = "llm_error", f"The language model could not be used, so no investigation was produced. {error}"
                break
            llm_calls += 1
            messages.append(LLMMessage(role="assistant", text=response.text or None, tool_calls=response.tool_calls))

            if not response.tool_calls:
                status, final_answer = "completed", response.text.strip()
                if response.stop_reason == "max_tokens":
                    warnings.append("The model reached its output limit; the answer may be cut off.")
                if not final_answer:
                    warnings.append("The model returned an empty answer.")
                break
            messages.append(LLMMessage(role="user", tool_results=self._run_tools(response.tool_calls, activities)))

        if status == "stopped_max_steps":
            final_answer = (f"The investigation stopped after {self.max_steps} model steps without a final "
                            "answer. The tool activity so far is listed.")
            warnings.append("Step limit reached before the model produced a final answer.")

        ungrounded = find_ungrounded_numbers(final_answer, activities) if status == "completed" else []
        if ungrounded:
            warnings.append("Some numbers in the answer could not be matched to any tool output: "
                            + ", ".join(ungrounded) + ". Check them against the tool activity before relying on them.")
        return InvestigationResult(
            question=question, status=status, final_answer=final_answer, tool_activity=activities,
            llm_calls=llm_calls, provider=self.provider.name, ungrounded_numbers=ungrounded, warnings=warnings,
        )

    def _run_tools(self, calls: list[Any], activities: list[ToolActivity]) -> list[ToolResultBlock]:
        blocks: list[ToolResultBlock] = []
        for call in calls:
            started = dt.datetime.now(dt.timezone.utc)
            clock = time.perf_counter()
            outcome = self.registry.run(call.name, call.arguments)
            activities.append(ToolActivity(
                step=len(activities) + 1, tool_name=call.name, tool_input=call.arguments,
                status="completed" if outcome.ok else "failed", error_type=outcome.error_type,
                summary=outcome.summary, started_at=started,
                duration_ms=(time.perf_counter() - clock) * 1000, output=outcome.output,
            ))
            blocks.append(ToolResultBlock(tool_call_id=call.id, content=outcome.content, is_error=not outcome.ok))
        return blocks


# --------------------------------------------------------------------------- command line


def main(argv: list[str] | None = None) -> int:
    """Manual check: run one investigation and print the activity log and the answer."""
    parser = argparse.ArgumentParser(description="Run one RiskSignal investigation.")
    parser.add_argument("question", nargs="?", default="Investigate PAYMENT_ENGINE_01.")
    parser.add_argument("--mock", action="store_true", help="use the offline mock provider (no API key needed)")
    parser.add_argument("--stress", action="store_true", help="with --mock: also run the stress comparison")
    parser.add_argument("--model", default=None, help="Anthropic model name (default: ANTHROPIC_MODEL or built-in)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.mock:
        from risksignal.agent.mock_provider import provider_for_question
        provider: LLMProvider = provider_for_question(args.question, include_stress=True if args.stress else None)
    else:
        from risksignal.agent.anthropic_provider import AnthropicProvider
        try:
            provider = AnthropicProvider(model=args.model)
        except LLMProviderError as error:
            print(error)
            return 2

    result = Investigator(provider, build_default_registry()).investigate(args.question)
    print(f"Provider: {result.provider}   Status: {result.status}   Model calls: {result.llm_calls}\n")
    print("Tool activity:")
    for number, line in enumerate(result.activity_log(), start=1):
        print(f"  {number}. {line}")
    print(f"\n{result.final_answer}\n")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    print(f"\n{result.disclaimer}")
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
