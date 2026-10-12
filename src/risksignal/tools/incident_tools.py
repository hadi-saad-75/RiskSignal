"""Recent incident tool."""

from collections import Counter
from datetime import date

import pandas as pd

from risksignal.tools.context import ToolContext, check_months, guarded
from risksignal.tools.schemas import IncidentCounts, IncidentRecord, RecentIncidentsResult

_SELECT_INCIDENTS = (
    "SELECT incident_id, date, category, description, financial_loss, severity FROM incidents "
    "WHERE system_id = ? AND date > ? AND date <= ? ORDER BY date, incident_id"
)


def window_start(as_of: date, months: int) -> date:
    """The date ``months`` calendar months before ``as_of`` (the window excludes this day)."""
    return (pd.Timestamp(as_of) - pd.DateOffset(months=months)).date()


@guarded("get_recent_incidents")
def get_recent_incidents(ctx: ToolContext, system_id: str, months: int = 12) -> RecentIncidentsResult:
    """Incidents of the system in the last ``months`` months (up to the dataset's end date),
    oldest first, with simple counts.

    ``deployment_keyword_matches`` counts incidents whose description contains the word
    "deployment". It is a keyword match, because the data have no separate cause field.
    Everything returned is observed synthetic data.
    """
    ctx.get_system(system_id)
    months = check_months(months)
    start = window_start(ctx.as_of_date, months)
    rows = ctx.query(_SELECT_INCIDENTS, (system_id, start.isoformat(), ctx.as_of_date.isoformat()))
    incidents = [
        IncidentRecord(
            incident_id=r["incident_id"], date=r["date"], category=r["category"],
            description=r["description"], financial_loss=r["financial_loss"], severity=r["severity"],
            mentions_deployment="deployment" in r["description"].lower(),
        )
        for r in rows
    ]
    return RecentIncidentsResult(
        tool_name="get_recent_incidents",
        system_id=system_id,
        months=months,
        window_start_exclusive=start,
        window_end_inclusive=ctx.as_of_date,
        incidents=incidents,
        counts=IncidentCounts(
            total=len(incidents),
            by_category=dict(sorted(Counter(i.category for i in incidents).items())),
            by_severity=dict(sorted(Counter(i.severity for i in incidents).items())),
            deployment_keyword_matches=sum(i.mentions_deployment for i in incidents),
            total_financial_loss=sum(i.financial_loss for i in incidents),
        ),
    )
