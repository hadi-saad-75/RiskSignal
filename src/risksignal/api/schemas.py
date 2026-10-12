"""Request and response models for the API.

Responses of the data and simulation endpoints reuse the tool-layer result models, so the API
adds no second definition of any business object. This module defines only what is specific
to HTTP: request bodies, the health report, the agent response and the error format.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from risksignal.agent.schemas import AGENT_DISCLAIMER, InvestigationStatus, ToolActivity
from risksignal.tools.context import (
    DEFAULT_SEED,
    DEFAULT_SIMULATIONS,
    MAX_SIMULATIONS,
    MIN_SIMULATIONS,
)


class _Request(BaseModel):
    """Request bodies are strict: wrong types and unknown fields are rejected (HTTP 422)."""

    model_config = ConfigDict(extra="forbid", strict=True)


class SimulationRequest(_Request):
    system_id: str = Field(min_length=1, max_length=100, examples=["PAYMENT_ENGINE_01"])
    number_of_simulations: int = Field(default=DEFAULT_SIMULATIONS, ge=MIN_SIMULATIONS, le=MAX_SIMULATIONS)
    random_seed: int = Field(default=DEFAULT_SEED, ge=0, le=2**32 - 1)


class ScenarioCompareRequest(SimulationRequest):
    scenario_id: str = Field(min_length=1, max_length=100, examples=["SHARED_VENDOR_OUTAGE"])


class CustomScenarioRequest(SimulationRequest):
    """Explicit numeric stress assumptions supplied by a person. Ranges are checked by the
    scenario model (guard rails against typos and overflow, not statements about realism)."""

    lambda_multiplier: float = Field(default=1.0, allow_inf_nan=False, description="Multiplies the incident rate.")
    severity_mu_shift: float = Field(default=0.0, allow_inf_nan=False, description="Added to mu (log space).")
    severity_sigma_multiplier: float = Field(default=1.0, allow_inf_nan=False, description="Multiplies sigma.")


class InvestigationRequest(_Request):
    question: str = Field(min_length=3, max_length=2000, examples=["Investigate PAYMENT_ENGINE_01."])
    include_tool_outputs: bool = Field(
        default=False,
        description="Also return the full structured output of every tool call (larger response).",
    )


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "risksignal"
    version: str
    database_available: bool
    llm_provider: str
    llm_configured: bool
    data_notice: str = "All data are synthetic (fictional Atlas Bank). Model parameters are illustrative."


class InvestigationResponse(BaseModel):
    """The agent's answer plus everything a UI needs to show how it arose."""

    question: str
    status: InvestigationStatus
    final_response: str
    activity_log: list[str] = Field(description="One concise line per tool call, ready to display.")
    tool_activity: list[ToolActivity] = Field(
        description="Each tool call with its input, status, timing and (optionally) full output."
    )
    warnings: list[str]
    ungrounded_numbers: list[str] = Field(
        description="Numbers in the answer that match no tool output. Best-effort check."
    )
    provider: str
    llm_calls: int
    disclaimer: str = AGENT_DISCLAIMER


class ErrorBody(BaseModel):
    type: str
    message: str
    suggestions: list[str] = Field(default_factory=list)
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Every error uses this shape. It never contains stack traces or internal detail."""

    error: ErrorBody


# For OpenAPI documentation of the error cases.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Unknown system or scenario (suggestions are included)."},
    422: {"model": ErrorResponse, "description": "Invalid request or simulation parameters."},
    503: {"model": ErrorResponse, "description": "Database or language model not available."},
}
