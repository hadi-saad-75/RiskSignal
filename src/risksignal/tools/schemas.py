"""Result types for the deterministic tool layer.

Every tool returns either a success model or a ``ToolError``; the field ``ok`` tells them
apart (``ok=True`` / ``ok=False``). Tools never raise exceptions to their caller.

Every success model says what kind of content it carries:

* ``data_kind = "observed_synthetic_data"``: rows and counts read from the synthetic Atlas
  Bank database (or its dependency graph). Observed in the synthetic world, never real.
* ``data_kind = "modelled_output"``: numbers produced by the stochastic engine under
  stated, illustrative assumptions. Simulation results sit in their own section, apart
  from the observed basis and the model assumptions.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risksignal.graph.schemas import (
    IndirectVendor,
    ProcessRef,
    RelatedSystem,
    SharedVendor,
    SystemControls,
    SystemLink,
    VendorRef,
)
from risksignal.stochastic.schemas import (
    FrequencyMethod,
    LossHistogram,
    LossMetrics,
    MetricDifferences,
    MetricPercentChanges,
    ModelParameters,
    ParameterChanges,
    Scenario,
    SeverityDataSource,
)

OBSERVED_NOTICE = "Synthetic Atlas Bank data. Not real, not realistic, and not evidence of predictive performance."
MODELLED_NOTICE = (
    "Modelled output under illustrative assumptions fitted to synthetic data. "
    "Not a forecast, not calibrated to any institution, and not a regulatory capital figure."
)

ToolErrorType = Literal[
    "unknown_system",
    "unknown_scenario",
    "invalid_argument",
    "model_error",
    "data_unavailable",
    "internal_error",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolError(_Model):
    """A typed, user-readable failure. Contains no stack trace or internal detail."""

    ok: Literal[False] = False
    tool_name: str
    error_type: ToolErrorType
    message: str
    suggestions: list[str] = Field(default_factory=list)


class _ToolResult(_Model):
    ok: Literal[True] = True
    tool_name: str


# --------------------------------------------------------------------------- system profile


class SystemDetails(_Model):
    system_id: str
    name: str
    description: str
    criticality: str


class ProcessDetails(_Model):
    process_id: str
    name: str
    description: str


class SystemMetadata(_Model):
    total_incidents_recorded: int
    number_of_controls: int
    kris_tracked: list[str]
    data_window_start: dt.date
    data_window_end: dt.date
    data_source: str = "Synthetic Atlas Bank (fictional institution)"


class SystemProfileResult(_ToolResult):
    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system: SystemDetails
    primary_process: ProcessDetails
    metadata: SystemMetadata


class SystemSummary(_Model):
    system_id: str
    name: str
    criticality: str
    primary_process_id: str
    primary_process_name: str


class SystemListResult(_ToolResult):
    """All systems in the database. Not offered to the agent; used by the API and UI."""

    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    systems: list[SystemSummary]


class OverviewCounts(_Model):
    systems: int
    processes: int
    vendors: int
    controls: int
    incidents: int
    kri_observations: int
    overdue_controls: int
    total_recorded_loss: float
    data_window_start: dt.date
    data_window_end: dt.date


class OverviewIncident(_Model):
    incident_id: str
    date: dt.date
    system_id: str
    system_name: str
    category: str
    severity: str
    financial_loss: float
    description: str


class BankOverviewResult(_ToolResult):
    """Bank-wide counts and the most recent incidents. Not offered to the agent; used by the UI."""

    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    counts: OverviewCounts
    recent_incidents: list[OverviewIncident]


# --------------------------------------------------------------------------- incidents


class IncidentRecord(_Model):
    incident_id: str
    date: dt.date
    category: str
    description: str
    financial_loss: float
    severity: str
    mentions_deployment: bool = Field(
        description="True if the free-text description contains the word 'deployment' "
        "(a keyword match; the data have no separate cause field)."
    )


class IncidentCounts(_Model):
    total: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    deployment_keyword_matches: int
    total_financial_loss: float


class RecentIncidentsResult(_ToolResult):
    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system_id: str
    months: int
    window_start_exclusive: dt.date
    window_end_inclusive: dt.date
    incidents: list[IncidentRecord]
    counts: IncidentCounts


# --------------------------------------------------------------------------- KRIs


class KriPoint(_Model):
    date: dt.date
    value: float


class KriSeries(_Model):
    """One KRI over the recent window, with plain descriptive statistics.

    ``previous_window_mean`` is the mean of the same number of observations immediately
    before the window (``None`` if the history is too short). All five KRIs in this
    dataset are such that higher values are less favourable.
    """

    kri_name: str
    observations: list[KriPoint]
    latest_value: float
    window_mean: float
    window_min: float
    window_max: float
    previous_window_mean: float | None
    change_vs_previous_window_percent: float | None


class KriHistoryResult(_ToolResult):
    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system_id: str
    months: int
    series: list[KriSeries]


# --------------------------------------------------------------------------- controls


class ControlRecord(_Model):
    control_id: str
    name: str
    description: str
    control_type: str
    last_review_date: dt.date
    review_status: str
    days_since_last_review: int


class ControlsResult(_ToolResult):
    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system_id: str
    as_of_date: dt.date
    controls: list[ControlRecord]
    counts_by_review_status: dict[str, int]
    overdue_control_ids: list[str]
    due_control_ids: list[str]


# --------------------------------------------------------------------------- dependencies


class DependenciesResult(_ToolResult):
    """Structural facts from the synthetic dependency graph. Not a statement about causation."""

    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system_id: str
    vendors: list[VendorRef]
    supported_processes: list[ProcessRef]
    controls: SystemControls
    shared_vendors: list[SharedVendor]
    related_systems: list[RelatedSystem]
    upstream_systems: list[SystemLink]
    downstream_systems: list[SystemLink]
    indirect_vendors: list[IndirectVendor]


# --------------------------------------------------------------------------- simulation


class ObservedBasis(_Model):
    """The synthetic observations that the model parameters were estimated from."""

    observed_incident_count: int
    observation_years: float
    severity_losses_used: int
    severity_data_source: SeverityDataSource
    severity_data_description: str
    severity_fallback_notes: list[str]


class ModelAssumptions(_Model):
    """Model form, parameter values and where each came from. All illustrative."""

    frequency_model: str = "Poisson(lambda) incidents per year"
    severity_model: str = "Lognormal(mu, sigma) loss per incident, parameters in log space"
    lambda_used: float
    lambda_source: FrequencyMethod
    lambda_historical: float | None
    frequency_note: str
    severity_mu: float
    severity_sigma: float
    number_of_simulations: int
    random_seed: int
    assumption_statements: list[str]


class SimulationOutputs(_Model):
    """Simulated annual aggregate loss distribution summaries."""

    metrics: LossMetrics
    analytic_mean_annual_loss: float
    histogram: LossHistogram | None


class LossSimulationResult(_ToolResult):
    data_kind: Literal["modelled_output"] = "modelled_output"
    notice: str = MODELLED_NOTICE
    system_id: str
    observed_basis: ObservedBasis
    model_assumptions: ModelAssumptions
    simulation_results: SimulationOutputs


class StressAssumptions(_Model):
    """Stress scenario assumptions: explicit, illustrative numbers applied to the baseline."""

    scenario: Scenario
    stress_parameters: ModelParameters
    parameter_changes: ParameterChanges
    label: str = "Stress scenario assumptions (illustrative, not calibrated)"


class ScenarioOutputs(_Model):
    baseline_metrics: LossMetrics
    stress_metrics: LossMetrics
    absolute_differences: MetricDifferences
    percentage_differences: MetricPercentChanges
    baseline_analytic_mean_annual_loss: float
    stress_analytic_mean_annual_loss: float
    baseline_histogram: LossHistogram | None
    stress_histogram: LossHistogram | None


class ScenarioComparisonResult(_ToolResult):
    data_kind: Literal["modelled_output"] = "modelled_output"
    notice: str = MODELLED_NOTICE
    system_id: str
    observed_basis: ObservedBasis
    baseline_assumptions: ModelAssumptions
    stress_assumptions: StressAssumptions
    simulation_results: ScenarioOutputs


class ScenarioListResult(_ToolResult):
    """The predefined illustrative scenarios and their assumptions. Not offered to the agent."""

    data_kind: Literal["illustrative_assumptions"] = "illustrative_assumptions"
    notice: str = (
        "Illustrative scenario assumptions chosen to demonstrate mechanics. Not calibrated, "
        "not expert-validated, and no institutional validity."
    )
    scenarios: list[Scenario]
