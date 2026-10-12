"""Read-only endpoints about systems: list, profile, incidents, controls, dependencies, KRIs.

Each endpoint calls the matching tool from ``risksignal.tools`` and returns its result.
"""

from fastapi import APIRouter, Depends, Query

from risksignal.api.dependencies import get_tool_context, unwrap_tool_result
from risksignal.api.schemas import ERROR_RESPONSES
from risksignal.tools.context import MAX_MONTHS, ToolContext
from risksignal.tools.control_tools import get_controls
from risksignal.tools.graph_tools import get_dependencies
from risksignal.tools.incident_tools import get_recent_incidents
from risksignal.tools.kri_tools import get_kri_history
from risksignal.tools.schemas import (
    BankOverviewResult,
    ControlsResult,
    DependenciesResult,
    KriHistoryResult,
    RecentIncidentsResult,
    SystemListResult,
    SystemProfileResult,
)
from risksignal.tools.system_tools import get_bank_overview, get_system_profile, list_systems

router = APIRouter(prefix="/systems", tags=["systems"], responses=ERROR_RESPONSES)
overview_router = APIRouter(tags=["overview"], responses=ERROR_RESPONSES)

Months = Query(12, ge=1, le=MAX_MONTHS, description="How many months back from the end of the data.")


@overview_router.get("/overview", response_model=BankOverviewResult, summary="Bank overview")
def overview(
    recent_incidents: int = Query(10, ge=1, le=100, description="How many recent incidents to return."),
    ctx: ToolContext = Depends(get_tool_context),
) -> BankOverviewResult:
    """Counts of systems, processes, vendors, controls and incidents, and the latest incidents."""
    return unwrap_tool_result(get_bank_overview(ctx, recent_incidents))


@router.get("", response_model=SystemListResult, summary="List systems")
def list_all_systems(ctx: ToolContext = Depends(get_tool_context)) -> SystemListResult:
    """All systems in the synthetic Atlas Bank database."""
    return unwrap_tool_result(list_systems(ctx))


@router.get("/{system_id}", response_model=SystemProfileResult, summary="System profile")
def system_profile(system_id: str, ctx: ToolContext = Depends(get_tool_context)) -> SystemProfileResult:
    """Details, criticality, primary business process and basic metadata."""
    return unwrap_tool_result(get_system_profile(ctx, system_id))


@router.get("/{system_id}/incidents", response_model=RecentIncidentsResult, summary="Recent incidents")
def system_incidents(
    system_id: str, months: int = Months, ctx: ToolContext = Depends(get_tool_context)
) -> RecentIncidentsResult:
    """Incident records for the last ``months`` months, with counts."""
    return unwrap_tool_result(get_recent_incidents(ctx, system_id, months))


@router.get("/{system_id}/controls", response_model=ControlsResult, summary="Controls")
def system_controls(system_id: str, ctx: ToolContext = Depends(get_tool_context)) -> ControlsResult:
    """Controls attached to the system with their review status."""
    return unwrap_tool_result(get_controls(ctx, system_id))


@router.get("/{system_id}/dependencies", response_model=DependenciesResult, summary="Dependencies")
def system_dependencies(system_id: str, ctx: ToolContext = Depends(get_tool_context)) -> DependenciesResult:
    """Vendors, processes, controls and related systems from the dependency graph."""
    return unwrap_tool_result(get_dependencies(ctx, system_id))


@router.get("/{system_id}/kri", response_model=KriHistoryResult, summary="KRI history")
def system_kri(
    system_id: str, months: int = Months, ctx: ToolContext = Depends(get_tool_context)
) -> KriHistoryResult:
    """Recent monthly KRI observations grouped by KRI."""
    return unwrap_tool_result(get_kri_history(ctx, system_id, months))
