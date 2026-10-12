"""Controls tool."""

from datetime import date

from risksignal.tools.context import ToolContext, guarded
from risksignal.tools.schemas import ControlRecord, ControlsResult

_SELECT_CONTROLS = (
    "SELECT control_id, name, description, control_type, last_review_date, review_status "
    "FROM controls WHERE system_id = ? ORDER BY control_id"
)


@guarded("get_controls")
def get_controls(ctx: ToolContext, system_id: str) -> ControlsResult:
    """Controls attached to the system with their review status, as recorded in the data.

    ``days_since_last_review`` is measured to the dataset's end date. An overdue review is a
    reason to ask questions, not proof that the control has failed. Everything returned is
    observed synthetic data.
    """
    ctx.get_system(system_id)
    controls = [
        ControlRecord(
            control_id=r["control_id"], name=r["name"], description=r["description"],
            control_type=r["control_type"], last_review_date=r["last_review_date"],
            review_status=r["review_status"],
            days_since_last_review=(ctx.as_of_date - date.fromisoformat(r["last_review_date"])).days,
        )
        for r in ctx.query(_SELECT_CONTROLS, (system_id,))
    ]
    counts: dict[str, int] = {}
    for control in controls:
        counts[control.review_status] = counts.get(control.review_status, 0) + 1
    return ControlsResult(
        tool_name="get_controls",
        system_id=system_id,
        as_of_date=ctx.as_of_date,
        controls=controls,
        counts_by_review_status=dict(sorted(counts.items())),
        overdue_control_ids=[c.control_id for c in controls if c.review_status == "overdue"],
        due_control_ids=[c.control_id for c in controls if c.review_status == "due"],
    )
