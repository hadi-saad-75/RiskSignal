"""Pure display helpers for the UI: number formatting and parsing of the agent's answer.

Nothing here calculates risk figures. It only formats values that the API returned and
arranges text for display.
"""

import re
from typing import Any

BANNER_TEXT = "Research prototype based on synthetic Atlas Bank data; results are not calibrated to observed losses."
SIMULATION_NOTICE = "Simulation results are conditional on the stated assumptions and synthetic data."

SECTION_HEADINGS = (
    "Observed evidence",
    "Model assumptions",
    "Simulation results",
    "Connected exposures",
    "Suggested investigation questions",
    "Limitations",
)
METRIC_LABELS = (
    ("mean", "Mean annual loss"),
    ("median", "Median annual loss"),
    ("p95", "P95"),
    ("p99", "P99"),
    ("expected_shortfall_95", "Expected Shortfall 95%"),
    ("expected_shortfall_99", "Expected Shortfall 99%"),
)
_HEADING_LINE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[*_]{1,2})?\s*(?:\d+[.)]\s*)?(" + "|".join(SECTION_HEADINGS) + r")\s*:?\s*(?:[*_]{1,2})?\s*:?\s*$",
    re.IGNORECASE,
)


def format_amount(value: float | None) -> str:
    """Whole units with thousands separators, e.g. 896,435."""
    return "n/a" if value is None else f"{value:,.0f}"


def format_decimal(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def format_percent(value: float | None, digits: int = 1) -> str:
    """Signed percentage, e.g. +154.1%. ``None`` (undefined change) shows as n/a."""
    return "n/a" if value is None else f"{value:+,.{digits}f}%"


def label_for(name: str) -> str:
    """'failed_deployment_rate' -> 'Failed deployment rate'."""
    return name.replace("_", " ").capitalize()


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split an answer into (heading, body) pairs at the known section headings.

    Recognises plain, markdown-heading (``## Title``), bold and numbered forms, in any case.
    Text before the first heading is returned as "Summary". If no known heading is present the
    whole answer is returned as a single "Answer" section.
    """
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    preamble: list[str] = []
    for line in text.splitlines():
        match = _HEADING_LINE.match(line)
        if match:
            title = next(h for h in SECTION_HEADINGS if h.lower() == match.group(1).lower())
            current = (title, [])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    if not sections:
        return [("Answer", text.strip())] if text.strip() else []
    result = [(title, "\n".join(lines).strip()) for title, lines in sections]
    intro = "\n".join(preamble).strip()
    return ([("Summary", intro)] if intro else []) + result


def extract_simulation_metadata(tool_activity: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Model assumptions and headline metrics from the last simulation tool call, if any."""
    for activity in reversed(tool_activity):
        output = activity.get("output")
        if activity.get("status") != "completed" or not output:
            continue
        if activity["tool_name"] == "run_loss_simulation":
            assumptions, metrics, stress = output["model_assumptions"], output["simulation_results"]["metrics"], None
        elif activity["tool_name"] == "compare_baseline_and_stress":
            results = output["simulation_results"]
            assumptions, metrics, stress = output["baseline_assumptions"], results["baseline_metrics"], results["stress_metrics"]
        else:
            continue
        return {
            "tool": activity["tool_name"],
            "lambda_used": assumptions["lambda_used"],
            "lambda_source": assumptions["lambda_source"],
            "severity_mu": assumptions["severity_mu"],
            "severity_sigma": assumptions["severity_sigma"],
            "severity_data_source": output["observed_basis"]["severity_data_source"],
            "severity_losses_used": output["observed_basis"]["severity_losses_used"],
            "number_of_simulations": assumptions["number_of_simulations"],
            "random_seed": assumptions["random_seed"],
            "baseline_metrics": metrics,
            "stress_metrics": stress,
        }
    return None


def comparison_rows(results: dict[str, Any]) -> list[dict[str, str]]:
    """Rows for the baseline-versus-stress table, formatted for display."""
    rows = []
    for key, label in METRIC_LABELS:
        rows.append({
            "Metric": label,
            "Baseline": format_amount(results["baseline_metrics"][key]),
            "Stress": format_amount(results["stress_metrics"][key]),
            "Difference": format_amount(results["absolute_differences"][key]),
            "Change": format_percent(results["percentage_differences"][key]),
        })
    return rows
