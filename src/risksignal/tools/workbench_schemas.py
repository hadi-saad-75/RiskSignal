"""Typed evidence for analyst review, never automated risk decisions."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from risksignal.stochastic.schemas import TemporalDiagnostics
from risksignal.tools.schemas import (
    ControlsResult,
    DependenciesResult,
    OBSERVED_NOTICE,
    RecentIncidentsResult,
    SystemProfileResult,
)


class EvidenceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class MonitoringPoint(EvidenceModel):
    date: dt.date
    value: float
    baseline_dates: list[dt.date]
    baseline_median: float | None = None
    baseline_mad: float | None = None
    robust_score: float | None = None
    signal: Literal[
        "unusual_increase", "flat_baseline_increase", "within_baseline",
        "insufficient_history", "gapped_history",
    ]


class MonitoredKri(EvidenceModel):
    kri_name: str
    data_status: Literal["current", "stale", "missing", "not_applicable"]
    applicability_basis: str | None = None
    latest: MonitoringPoint | None
    scored_observations: int
    flagged_observations: int
    flag_rate: float | None
    history: list[MonitoringPoint]
    source_refs: list[str]


class KriMonitoringResult(EvidenceModel):
    ok: Literal[True] = True
    tool_name: Literal["get_kri_monitoring"] = "get_kri_monitoring"
    data_kind: Literal["observed_synthetic_data"] = "observed_synthetic_data"
    notice: str = OBSERVED_NOTICE
    system_id: str
    as_of_date: dt.date
    policy_version: str = "kri-mad-v1"
    baseline_months: int = 12
    minimum_history: int = 6
    score_threshold: float = 3.5
    evaluation_window_months: int = 12
    series: list[MonitoredKri]
    limitations: list[str]


class ModelDiagnosticsResult(TemporalDiagnostics):
    ok: Literal[True] = True
    tool_name: Literal["get_model_diagnostics"] = "get_model_diagnostics"
    data_kind: Literal["modelled_output"] = "modelled_output"
    notice: str = "Synthetic temporal holdout diagnostics, not independent validation or predictive performance."


class ReviewQuestion(EvidenceModel):
    topic: str
    question: str
    source_refs: list[str]


class RiskWorkpaperResult(EvidenceModel):
    ok: Literal[True] = True
    tool_name: Literal["get_risk_workpaper"] = "get_risk_workpaper"
    data_kind: Literal["mixed_evidence"] = "mixed_evidence"
    notice: str = OBSERVED_NOTICE
    status: Literal["draft_for_human_review"] = "draft_for_human_review"
    policy_version: str = "risk-workpaper-v1"
    system_id: str
    as_of_date: dt.date
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: SystemProfileResult
    incidents: RecentIncidentsResult
    controls: ControlsResult
    dependencies: DependenciesResult
    monitoring: KriMonitoringResult
    diagnostics: ModelDiagnosticsResult
    review_questions: list[ReviewQuestion]
    limitations: list[str]
