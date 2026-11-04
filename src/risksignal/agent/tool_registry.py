"""Registry connecting the language model to the deterministic RiskSignal tools.

The registry is the agent's only access to data and numbers. It publishes each tool's name,
description and JSON input schema to the model, checks the arguments the model supplies,
runs the real tool, and returns a JSON result the model can read. A one-line log message for
each call is written here in Python, from the tool's result, not by the model.
"""

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from risksignal.agent.base import ToolSpec
from risksignal.stochastic.scenario import PREDEFINED_SCENARIOS
from risksignal.tools.context import ToolContext
from risksignal.tools.control_tools import get_controls
from risksignal.tools.graph_tools import get_dependencies
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.kri_tools import get_kri_history
from risksignal.tools.schemas import ToolError
from risksignal.tools.simulation_tools import compare_baseline_and_stress, list_scenarios, run_loss_simulation
from risksignal.tools.system_tools import get_bank_overview, get_portfolio_summary, get_system_profile, list_systems

logger = logging.getLogger(__name__)

# Bulky chart data the model does not need in order to reason or write.
_OMITTED_FROM_MODEL_VIEW = {"histogram", "baseline_histogram", "stress_histogram"}
_MAX_LOG_MESSAGE = 160


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    function: Callable[..., Any]
    summarise: Callable[[dict[str, Any], Any], str]


@dataclass(frozen=True)
class ToolOutcome:
    """Everything the agent needs to know about one executed tool call."""

    result: BaseModel
    ok: bool
    error_type: str | None
    summary: str
    output: dict[str, Any]
    content: str  # JSON text sent back to the model


# --------------------------------------------------------------------------- model-facing view


def model_view(result: BaseModel) -> dict[str, Any]:
    """The tool result as plain JSON-able data, without chart histograms."""

    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in _OMITTED_FROM_MODEL_VIEW}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    return strip(result.model_dump(mode="json"))


# --------------------------------------------------------------------------- definitions

_SYSTEM_ID = {"type": "string", "description": "System identifier exactly as in the data, e.g. PAYMENT_ENGINE_01."}
_MONTHS = {"type": "integer", "minimum": 1, "maximum": 120, "default": 12,
           "description": "How many months back from the end of the data."}
_SIMULATIONS = {"type": "integer", "minimum": 1000, "maximum": 1_000_000, "default": 100_000,
                "description": "Number of simulated years."}
_SEED = {"type": "integer", "minimum": 0, "default": 42, "description": "Random seed (same seed, same result)."}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _summary_profile(args: dict[str, Any], r: Any) -> str:
    return f"Retrieved system profile for {r.system.system_id}"


def _summary_incidents(args: dict[str, Any], r: Any) -> str:
    return f"Retrieved {r.months} months of incidents ({r.counts.total} found)"


def _summary_kri(args: dict[str, Any], r: Any) -> str:
    return f"Retrieved {r.months} months of KRI history ({len(r.series)} indicators)"


def _summary_controls(args: dict[str, Any], r: Any) -> str:
    return f"Retrieved controls ({len(r.controls)} controls, {len(r.overdue_control_ids)} overdue)"


def _summary_dependencies(args: dict[str, Any], r: Any) -> str:
    return (f"Checked system dependencies ({len(r.vendors)} vendors, {len(r.shared_vendors)} shared vendors, "
            f"{len(r.related_systems)} related systems)")


def _summary_simulation(args: dict[str, Any], r: Any) -> str:
    settings = r.model_assumptions
    return f"Ran {settings.number_of_simulations:,} year Monte Carlo simulation (seed {settings.random_seed})"


def _summary_stress(args: dict[str, Any], r: Any) -> str:
    n = r.baseline_assumptions.number_of_simulations
    return (f"Compared baseline and stress scenario {r.stress_assumptions.scenario.scenario_id} "
            f"({n:,} simulated years each)")


def _summary_systems(args: dict[str, Any], r: Any) -> str:
    return f"Listed systems ({len(r.systems)} found)"


def _summary_portfolio(args: dict[str, Any], r: Any) -> str:
    return f"Compared all {r.totals.systems} systems over {r.months} months"


def _summary_overview(args: dict[str, Any], r: Any) -> str:
    return f"Retrieved bank-wide counts and the {len(r.recent_incidents)} most recent incidents"


def _summary_scenarios(args: dict[str, Any], r: Any) -> str:
    return f"Listed predefined stress scenarios ({len(r.scenarios)} found)"


def _definitions() -> list[ToolDefinition]:
    scenarios = sorted(PREDEFINED_SCENARIOS)
    return [
        ToolDefinition(
            "get_system_profile",
            "Get a system's details: name, description, criticality, primary business process and basic "
            "metadata (number of incidents and controls on record, KRIs tracked, data window). Synthetic data.",
            _schema({"system_id": _SYSTEM_ID}, ["system_id"]), get_system_profile, _summary_profile),
        ToolDefinition(
            "get_recent_incidents",
            "Get a system's incident records for the last N months with counts by category and severity, "
            "total financial loss and how many descriptions mention 'deployment'. Synthetic data.",
            _schema({"system_id": _SYSTEM_ID, "months": _MONTHS}, ["system_id"]),
            get_recent_incidents, _summary_incidents),
        ToolDefinition(
            "get_kri_history",
            "Get a system's recent monthly Key Risk Indicator values grouped by KRI, with latest value, "
            "window mean, min, max and the percentage change against the previous window. Synthetic data.",
            _schema({"system_id": _SYSTEM_ID, "months": _MONTHS}, ["system_id"]),
            get_kri_history, _summary_kri),
        ToolDefinition(
            "get_controls",
            "Get the controls attached to a system with type, last review date, review status "
            "(current, due, overdue) and days since review. Synthetic data.",
            _schema({"system_id": _SYSTEM_ID}, ["system_id"]), get_controls, _summary_controls),
        ToolDefinition(
            "get_dependencies",
            "Get a system's vendors, supported business processes, controls, vendors shared with other "
            "systems, related systems (shared vendor or process), upstream and downstream systems and "
            "indirectly reached vendors. Structural facts from synthetic data; sharing is a shared "
            "exposure, not evidence that one failure causes another.",
            _schema({"system_id": _SYSTEM_ID}, ["system_id"]), get_dependencies, _summary_dependencies),
        ToolDefinition(
            "run_loss_simulation",
            "Run the baseline Monte Carlo simulation of a system's annual aggregate loss (Poisson "
            "frequency, Lognormal severity, parameters estimated from synthetic history). Returns mean, "
            "median, P95, P99, Expected Shortfall 95 and 99 and the assumptions. Output under stated "
            "assumptions, not a forecast.",
            _schema({"system_id": _SYSTEM_ID, "number_of_simulations": _SIMULATIONS, "random_seed": _SEED},
                    ["system_id"]),
            run_loss_simulation, _summary_simulation),
        ToolDefinition(
            "compare_baseline_and_stress",
            "Compare the baseline simulation with a predefined illustrative stress scenario for a system "
            "(absolute and percentage differences). Scenario numbers are illustrative assumptions, not "
            "calibrated. Only predefined scenarios are available.",
            _schema({"system_id": _SYSTEM_ID,
                     "scenario_id": {"type": "string", "enum": scenarios, "description": "Predefined scenario."},
                     "number_of_simulations": _SIMULATIONS, "random_seed": _SEED},
                    ["system_id", "scenario_id"]),
            compare_baseline_and_stress, _summary_stress),
    ]


def _portfolio_definitions() -> list[ToolDefinition]:
    """Bank-wide tools offered only to the conversational assistant."""
    return [
        ToolDefinition(
            "list_systems",
            "List every system with its ID, name, criticality and primary business process. Use it to "
            "find the ID of a system the user names in words. Synthetic data.",
            _schema({}, []), list_systems, _summary_systems),
        ToolDefinition(
            "get_portfolio_summary",
            "Compare all systems over the last N months: incidents, high or critical incidents, recorded "
            "loss, incident count in the previous window of the same length and its change, and overdue or "
            "due control reviews, sorted by recorded loss (highest first), with bank-wide totals. Use it for "
            "questions across systems such as where to look first. Observable facts, not a risk score. "
            "Synthetic data.",
            _schema({"months": _MONTHS}, []), get_portfolio_summary, _summary_portfolio),
        ToolDefinition(
            "get_bank_overview",
            "Bank-wide counts (systems, processes, vendors, controls, incidents, overdue controls, total "
            "recorded loss, data window) and the most recent incidents across all systems. Synthetic data.",
            _schema({"recent_incidents": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10,
                                          "description": "How many of the latest incidents to return."}}, []),
            get_bank_overview, _summary_overview),
        ToolDefinition(
            "list_scenarios",
            "List the predefined illustrative stress scenarios with their multipliers and assumption notes. "
            "Scenario numbers are illustrative assumptions, not calibrated.",
            _schema({}, []), list_scenarios, _summary_scenarios),
    ]


# --------------------------------------------------------------------------- registry


class ToolRegistry:
    """Looks up and safely runs tools by name. ``run`` never raises."""

    def __init__(self, definitions: Sequence[ToolDefinition]) -> None:
        self._definitions = {d.name: d for d in definitions}

    @property
    def names(self) -> list[str]:
        return list(self._definitions)

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(name=d.name, description=d.description, input_schema=d.input_schema)
                for d in self._definitions.values()]

    def run(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        definition = self._definitions.get(name)
        if definition is None:
            return self._failure(name, "invalid_argument",
                                 f"Unknown tool '{name}'. Available tools: {', '.join(self.names)}.")
        problem = self._check_arguments(definition, arguments)
        if problem:
            return self._failure(name, "invalid_argument", problem)
        try:
            result = definition.function(**arguments)
        except Exception:  # tools already guard themselves; this is a last line of defence
            logger.exception("Tool %s raised unexpectedly", name)
            return self._failure(name, "internal_error", "The tool failed unexpectedly. No result was produced.")
        if isinstance(result, ToolError):
            return self._outcome(result, f"{name} failed ({result.error_type}): {result.message}", ok=False)
        return self._outcome(result, definition.summarise(arguments, result), ok=True)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _check_arguments(definition: ToolDefinition, arguments: Any) -> str | None:
        if not isinstance(arguments, dict):
            return "Tool arguments must be a JSON object."
        allowed = set(definition.input_schema["properties"])
        unexpected = sorted(set(arguments) - allowed)
        if unexpected:
            return f"Unexpected argument(s): {', '.join(unexpected)}. Allowed: {', '.join(sorted(allowed))}."
        missing = [k for k in definition.input_schema["required"] if k not in arguments]
        if missing:
            return f"Missing required argument(s): {', '.join(missing)}."
        return None

    def _failure(self, name: str, error_type: str, message: str) -> ToolOutcome:
        error = ToolError(tool_name=name, error_type=error_type, message=message)  # type: ignore[arg-type]
        return self._outcome(error, f"{name} failed ({error_type}): {message}", ok=False)

    @staticmethod
    def _outcome(result: BaseModel, summary: str, ok: bool) -> ToolOutcome:
        view = model_view(result)
        if len(summary) > _MAX_LOG_MESSAGE:
            summary = summary[: _MAX_LOG_MESSAGE - 3] + "..."
        return ToolOutcome(
            result=result, ok=ok, error_type=None if ok else view["error_type"], summary=summary,
            output=view, content=json.dumps(view, separators=(",", ":")),
        )


def _bind(definitions: list[ToolDefinition], ctx: ToolContext | None) -> ToolRegistry:
    context = ctx or ToolContext()
    return ToolRegistry([
        ToolDefinition(d.name, d.description, d.input_schema,
                       (lambda f: (lambda **kwargs: f(context, **kwargs)))(d.function), d.summarise)
        for d in definitions
    ])


def build_default_registry(ctx: ToolContext | None = None) -> ToolRegistry:
    """The seven RiskSignal tools bound to a database context (default: the Atlas Bank database)."""
    return _bind(_definitions(), ctx)


def build_chat_registry(ctx: ToolContext | None = None) -> ToolRegistry:
    """The seven investigation tools plus the bank-wide tools used by the conversational assistant."""
    return _bind(_definitions() + _portfolio_definitions(), ctx)
