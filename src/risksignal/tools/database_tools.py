"""Read-only, bounded browsing of the synthetic source tables."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from risksignal.data.schemas import TABLE_MODELS
from risksignal.tools.context import ToolContext, ToolFailure, check_int, guarded
from risksignal.tools.schemas import OBSERVED_NOTICE

DatabaseTable = Literal[
    "systems", "processes", "vendors", "controls", "incidents", "kri_observations", "dependencies",
]
_QUERIES = {
    "systems": ("SELECT COUNT(*) AS n FROM systems",
                "SELECT * FROM systems ORDER BY system_id LIMIT ? OFFSET ?"),
    "processes": ("SELECT COUNT(*) AS n FROM processes",
                  "SELECT * FROM processes ORDER BY process_id LIMIT ? OFFSET ?"),
    "vendors": ("SELECT COUNT(*) AS n FROM vendors",
                "SELECT * FROM vendors ORDER BY vendor_id LIMIT ? OFFSET ?"),
    "controls": ("SELECT COUNT(*) AS n FROM controls",
                 "SELECT * FROM controls ORDER BY control_id LIMIT ? OFFSET ?"),
    "incidents": ("SELECT COUNT(*) AS n FROM incidents",
                  "SELECT * FROM incidents ORDER BY incident_id LIMIT ? OFFSET ?"),
    "kri_observations": ("SELECT COUNT(*) AS n FROM kri_observations",
                        "SELECT * FROM kri_observations ORDER BY date,system_id,kri_name LIMIT ? OFFSET ?"),
    "dependencies": ("SELECT COUNT(*) AS n FROM dependencies",
                     "SELECT * FROM dependencies ORDER BY source_id,source_type,relation,target_id,target_type "
                     "LIMIT ? OFFSET ?"),
}


class DatabasePage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    table: DatabaseTable
    columns: list[str]
    rows: list[dict[str, str | int | float | None]]
    total_rows: int
    offset: int
    limit: int
    notice: str = OBSERVED_NOTICE


@guarded("browse_database")
def browse_database(ctx: ToolContext, table: DatabaseTable, offset: int = 0, limit: int = 100) -> DatabasePage:
    if table not in _QUERIES:
        raise ToolFailure("invalid_argument", "Choose a supported synthetic database table.")
    offset = check_int("offset", offset, 0, 2**31 - 1)
    limit = check_int("limit", limit, 1, 200)
    columns = list(TABLE_MODELS[table].model_fields)
    count_sql, page_sql = _QUERIES[table]
    count = ctx.query(count_sql)[0]["n"]
    rows = ctx.query(page_sql, (limit, offset))
    return DatabasePage(table=table, columns=columns, rows=[dict(row) for row in rows],
                        total_rows=count, offset=offset, limit=limit)
