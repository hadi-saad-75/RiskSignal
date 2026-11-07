"""Reproducible, read-only RCSA preparation, with source-linked human questions."""

import hashlib
import json
from typing import TypeVar

from risksignal.tools.context import ToolContext, ToolFailure, guarded
from risksignal.tools.control_tools import get_controls
from risksignal.tools.graph_tools import get_dependencies
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.monitoring_tools import FLAG_SIGNALS, get_kri_monitoring
from risksignal.tools.schemas import ToolError
from risksignal.tools.system_tools import get_system_profile
from risksignal.tools.validation_tools import get_model_diagnostics
from risksignal.tools.workbench_schemas import ReviewQuestion, RiskWorkpaperResult

T = TypeVar("T")


def _require(result: T | ToolError) -> T:
    if isinstance(result, ToolError):
        raise ToolFailure(result.error_type, f"{result.tool_name}: {result.message}", result.suggestions)
    return result


def evidence_digest(workpaper: RiskWorkpaperResult) -> str:
    """Content fingerprint, not a signature, immutable log or proof of authenticity."""
    content = workpaper.model_dump(mode="json", exclude={"evidence_sha256"})
    return hashlib.sha256(json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()


@guarded("get_risk_workpaper")
def get_risk_workpaper(ctx: ToolContext, system_id: str) -> RiskWorkpaperResult:
    """Prepare evidence for RCSA review without inferring control effectiveness or residual risk."""
    profile = _require(get_system_profile(ctx, system_id))
    incidents = _require(get_recent_incidents(ctx, system_id, 12))
    controls = _require(get_controls(ctx, system_id))
    dependencies = _require(get_dependencies(ctx, system_id))
    monitoring = _require(get_kri_monitoring(ctx, system_id))
    diagnostics = _require(get_model_diagnostics(ctx, system_id))
    questions = [
        ReviewQuestion(
            topic="Control evidence",
            question="Obtain design and operating-effectiveness test evidence, test population, exceptions and owner attestations. Review status alone does not establish effectiveness.",
            source_refs=[f"controls:{c.control_id}" for c in controls.controls],
        ),
        ReviewQuestion(
            topic="RCSA scope",
            question="Confirm the process owner, risk statement, inherent impact/likelihood, control-to-risk mapping and residual assessment using an approved institutional methodology.",
            source_refs=[f"systems:{system_id}", f"processes:{profile.primary_process.process_id}"],
        ),
    ]
    for control in controls.controls:
        if control.review_status in {"due", "overdue"}:
            questions.append(ReviewQuestion(
                topic="Review follow-up",
                question=f"Confirm the review owner and supporting evidence for {control.control_id}, recorded as {control.review_status}. Has the review been scheduled or completed?",
                source_refs=[f"controls:{control.control_id}"],
            ))
    for series in monitoring.series:
        if series.data_status not in {"current", "not_applicable"} or (
            series.latest is not None
            and series.latest.signal in FLAG_SIGNALS | {"insufficient_history", "gapped_history"}
        ):
            questions.append(ReviewQuestion(
                topic="KRI challenge",
                question=f"Investigate {series.kri_name}: data status {series.data_status}, latest signal "
                         f"{series.latest.signal if series.latest else 'no_observation'}. Confirm data quality and business context before escalation.",
                source_refs=series.source_refs[-13:],
            ))
    if incidents.incidents:
        questions.append(ReviewQuestion(
            topic="Incident learning",
            question="Review incident narratives and obtain root-cause and remediation evidence. Do not infer causes or control failures from temporal co-occurrence.",
            source_refs=[f"incidents:{i.incident_id}" for i in incidents.incidents],
        ))
    if dependencies.shared_vendors:
        questions.append(ReviewQuestion(
            topic="Resilience and third parties",
            question="Check shared-provider contingency plans, important business services, impact tolerances and exercise evidence with the service owner. A dependency graph alone is not a resilience assessment.",
            source_refs=[f"vendors:{s.vendor.vendor_id}" for s in dependencies.shared_vendors],
        ))
    result = RiskWorkpaperResult(
        system_id=system_id, as_of_date=ctx.as_of_date, evidence_sha256="0" * 64,
        profile=profile, incidents=incidents, controls=controls, dependencies=dependencies,
        monitoring=monitoring, diagnostics=diagnostics, review_questions=questions,
        limitations=[
            "Draft RCSA preparation only. No risk rating, control effectiveness, approval, closure or compliance determination is made.",
            "No control test results, risk owners, approved appetite limits, remediation records or real loss data are available.",
            "All records are synthetic. Losses have synthetic monetary units, not an asserted currency.",
            "The content fingerprint supports reproduction, not tamper-proof storage or reviewer authentication.",
            "The local demo assumes a static dataset while evidence is gathered, not a transactional production snapshot.",
        ],
    )
    return result.model_copy(update={"evidence_sha256": evidence_digest(result)})
