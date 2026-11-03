"""System tools: profile, system list and bank overview."""

from risksignal.tools.context import ToolContext, ToolFailure, check_int, guarded
from risksignal.tools.schemas import (
    BankOverviewResult,
    OverviewCounts,
    OverviewIncident,
    ProcessDetails,
    SystemDetails,
    SystemListResult,
    SystemMetadata,
    SystemProfileResult,
    SystemSummary,
)

_SELECT_PROCESS = "SELECT process_id, name, description FROM processes WHERE process_id = ?"
_SELECT_SYSTEMS = (
    "SELECT s.system_id, s.name, s.criticality, s.primary_process_id, p.name AS primary_process_name "
    "FROM systems s JOIN processes p ON p.process_id = s.primary_process_id ORDER BY s.system_id"
)
_COUNT_INCIDENTS = "SELECT COUNT(*) AS n FROM incidents WHERE system_id = ?"
_COUNT_CONTROLS = "SELECT COUNT(*) AS n FROM controls WHERE system_id = ?"
_SELECT_KRI_NAMES = "SELECT DISTINCT kri_name FROM kri_observations WHERE system_id = ? ORDER BY kri_name"

# Table names cannot be bound parameters, so each count is its own fixed statement.
_OVERVIEW_COUNTS = {
    "systems": "SELECT COUNT(*) AS n FROM systems",
    "processes": "SELECT COUNT(*) AS n FROM processes",
    "vendors": "SELECT COUNT(*) AS n FROM vendors",
    "controls": "SELECT COUNT(*) AS n FROM controls",
    "incidents": "SELECT COUNT(*) AS n FROM incidents",
    "kri_observations": "SELECT COUNT(*) AS n FROM kri_observations",
}
_OVERVIEW_SUMMARY = {
    "overdue_controls": "SELECT COUNT(*) AS n FROM controls WHERE review_status = 'overdue'",
    "total_recorded_loss": "SELECT COALESCE(SUM(financial_loss), 0.0) AS n FROM incidents",
}
_SELECT_RECENT_INCIDENTS = (
    "SELECT i.incident_id, i.date, i.system_id, s.name AS system_name, i.category, i.severity, "
    "i.financial_loss, i.description FROM incidents i JOIN systems s ON s.system_id = i.system_id "
    "ORDER BY i.date DESC, i.incident_id DESC LIMIT ?"
)


@guarded("get_bank_overview")
def get_bank_overview(ctx: ToolContext, recent_incidents: int = 10) -> BankOverviewResult:
    """Counts of systems, processes, vendors, controls, incidents and KRI observations, plus the
    most recent incidents across the bank.

    Used by the UI. It is not a tool offered to the agent. Observed synthetic data only.
    """
    limit = check_int("recent_incidents", recent_incidents, 1, 100)
    counts = {name: ctx.query(sql)[0]["n"] for name, sql in _OVERVIEW_COUNTS.items()}
    summary = {name: ctx.query(sql)[0]["n"] for name, sql in _OVERVIEW_SUMMARY.items()}
    return BankOverviewResult(
        tool_name="get_bank_overview",
        counts=OverviewCounts(
            **counts,
            **summary,
            data_window_start=ctx.observation_start,
            data_window_end=ctx.as_of_date,
        ),
        recent_incidents=[OverviewIncident(**dict(row)) for row in ctx.query(_SELECT_RECENT_INCIDENTS, (limit,))],
    )


@guarded("list_systems")
def list_systems(ctx: ToolContext) -> SystemListResult:
    """All systems with criticality and primary business process, sorted by ID.

    Used by the API and UI to let a person pick a system. It is not a tool offered to the agent.
    """
    return SystemListResult(
        tool_name="list_systems",
        systems=[SystemSummary(**dict(row)) for row in ctx.query(_SELECT_SYSTEMS)],
    )


@guarded("get_system_profile")
def get_system_profile(ctx: ToolContext, system_id: str) -> SystemProfileResult:
    """System details, criticality, primary business process and basic metadata.

    Everything returned is observed synthetic data.
    """
    system = ctx.get_system(system_id)
    process_rows = ctx.query(_SELECT_PROCESS, (system["primary_process_id"],))
    if not process_rows:
        raise ToolFailure("data_unavailable", f"The primary process of {system_id} is missing from the database.")
    process = process_rows[0]
    return SystemProfileResult(
        tool_name="get_system_profile",
        system=SystemDetails(
            system_id=system["system_id"], name=system["name"],
            description=system["description"], criticality=system["criticality"],
        ),
        primary_process=ProcessDetails(
            process_id=process["process_id"], name=process["name"], description=process["description"],
        ),
        metadata=SystemMetadata(
            total_incidents_recorded=ctx.query(_COUNT_INCIDENTS, (system_id,))[0]["n"],
            number_of_controls=ctx.query(_COUNT_CONTROLS, (system_id,))[0]["n"],
            kris_tracked=[r["kri_name"] for r in ctx.query(_SELECT_KRI_NAMES, (system_id,))],
            data_window_start=ctx.observation_start,
            data_window_end=ctx.as_of_date,
        ),
    )
