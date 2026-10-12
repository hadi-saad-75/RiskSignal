"""Result types for the investigation agent."""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AGENT_DISCLAIMER = (
    "All data are synthetic (fictional Atlas Bank) and all model parameters are illustrative. "
    "Simulation results are outputs under stated modelling assumptions, not forecasts. "
    "This assistant supports human analysts and makes no risk decisions."
)

InvestigationStatus = Literal["completed", "stopped_max_steps", "llm_error"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolActivity(_Model):
    """One tool call made during an investigation: what was asked, whether it worked, when.

    ``summary`` is a short log line written by Python (not by the language model) and is
    suitable for display in a UI. ``output`` is the structured result the model received
    (large histograms are left out of what the model sees), kept so that every statement in
    the answer can be audited against it.
    """

    step: int = Field(description="1-based order of the tool call within the investigation.")
    tool_name: str
    tool_input: dict[str, Any]
    status: Literal["completed", "failed"]
    error_type: str | None = None
    summary: str
    started_at: dt.datetime
    duration_ms: float
    output: dict[str, Any] | None = None


class InvestigationResult(_Model):
    """The outcome of one investigation: the answer plus an auditable record of how it arose."""

    question: str
    status: InvestigationStatus
    final_answer: str
    tool_activity: list[ToolActivity]
    llm_calls: int
    provider: str
    ungrounded_numbers: list[str] = Field(
        default_factory=list,
        description="Numbers in the answer that could not be matched to any tool output "
        "(best-effort check; an empty list is not proof that every statement is right).",
    )
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = AGENT_DISCLAIMER

    def activity_log(self) -> list[str]:
        """Concise, UI-ready lines describing the tool activity."""
        return [a.summary for a in self.tool_activity]
