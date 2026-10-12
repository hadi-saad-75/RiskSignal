"""KRI history tool."""

from itertools import groupby
from statistics import fmean

from risksignal.tools.context import ToolContext, check_months, guarded
from risksignal.tools.schemas import KriHistoryResult, KriPoint, KriSeries

_SELECT_KRIS = (
    "SELECT kri_name, date, value FROM kri_observations WHERE system_id = ? ORDER BY kri_name, date"
)


def _percent_change(previous: float | None, current: float) -> float | None:
    if previous is None or previous == 0:
        return None
    return 100.0 * (current - previous) / previous


def _build_series(kri_name: str, points: list[KriPoint], months: int) -> KriSeries:
    """Last ``months`` monthly observations, compared with the ``months`` just before them."""
    window = points[-months:]
    previous = points[-2 * months:-months]
    values = [p.value for p in window]
    previous_mean = fmean(p.value for p in previous) if len(previous) == months else None
    window_mean = fmean(values)
    return KriSeries(
        kri_name=kri_name,
        observations=window,
        latest_value=values[-1],
        window_mean=window_mean,
        window_min=min(values),
        window_max=max(values),
        previous_window_mean=previous_mean,
        change_vs_previous_window_percent=_percent_change(previous_mean, window_mean),
    )


@guarded("get_kri_history")
def get_kri_history(ctx: ToolContext, system_id: str, months: int = 12) -> KriHistoryResult:
    """Recent monthly KRI observations of the system, grouped by KRI.

    The last ``months`` monthly observations of each KRI are returned (oldest first) with the
    latest value, window mean, minimum and maximum, and the percentage change of the window
    mean against the preceding window of the same length. Everything returned is observed
    synthetic data; no trend is projected.
    """
    ctx.get_system(system_id)
    months = check_months(months)
    rows = ctx.query(_SELECT_KRIS, (system_id,))
    series = [
        _build_series(name, [KriPoint(date=r["date"], value=r["value"]) for r in group], months)
        for name, group in groupby(rows, key=lambda r: r["kri_name"])
    ]
    return KriHistoryResult(tool_name="get_kri_history", system_id=system_id, months=months, series=series)
