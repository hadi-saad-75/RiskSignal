"""Past-only robust KRI monitoring with explicit missing-data and evaluation states."""

import math
from datetime import date
from statistics import median
from typing import get_args

from risksignal.data.schemas import KriName
from risksignal.tools.context import ToolContext, ToolFailure, guarded
from risksignal.tools.incident_tools import window_start
from risksignal.tools.workbench_schemas import (
    KriMonitoringResult,
    MonitoredKri,
    MonitoringPoint,
)

BASELINE_MONTHS = 12
MINIMUM_HISTORY = 6
SCORE_THRESHOLD = 3.5
MAD_SCALE = 1.4826
FLAG_SIGNALS = {"unusual_increase", "flat_baseline_increase"}
SCORED_SIGNALS = FLAG_SIGNALS | {"within_baseline"}


def _month(day: date) -> int:
    return day.year * 12 + day.month


def monitor_points(points: list[tuple[date, float]]) -> list[MonitoringPoint]:
    """Score each observation using only contiguous earlier calendar months.

    All existing Atlas Bank KRIs are adverse when higher. A flat baseline has no
    estimable robust scale, so an increase is identified without inventing a z-score.
    """
    ordered = sorted(points)
    if len({_month(day) for day, _ in ordered}) != len(ordered):
        raise ValueError("KRI observations must have unique calendar months.")
    if any(not math.isfinite(value) or value < 0 for _, value in ordered):
        raise ValueError("KRI values must be finite and non-negative.")
    result: list[MonitoringPoint] = []
    for index, (day, value) in enumerate(ordered):
        prior = [(d, v) for d, v in ordered[:index] if 0 < _month(day) - _month(d) <= BASELINE_MONTHS]
        dates = [d for d, _ in prior]
        base = dict(date=day, value=value, baseline_dates=dates)
        if len(prior) < MINIMUM_HISTORY:
            result.append(MonitoringPoint(**base, signal="insufficient_history"))
            continue
        if [_month(d) for d in dates] != list(range(_month(day) - len(prior), _month(day))):
            result.append(MonitoringPoint(**base, signal="gapped_history"))
            continue
        centre = float(median(v for _, v in prior))
        mad = float(median(abs(v - centre) for _, v in prior))
        if mad == 0:
            result.append(MonitoringPoint(
                **base, baseline_median=centre, baseline_mad=mad,
                signal="flat_baseline_increase" if value > centre else "within_baseline",
            ))
        else:
            score = (value - centre) / (MAD_SCALE * mad)
            result.append(MonitoringPoint(
                **base, baseline_median=centre, baseline_mad=mad, robust_score=score,
                signal="unusual_increase" if score > SCORE_THRESHOLD else "within_baseline",
            ))
    return result


@guarded("get_kri_monitoring")
def get_kri_monitoring(ctx: ToolContext, system_id: str) -> KriMonitoringResult:
    """Explainable review signals, not forecasts, appetite breaches or incident probabilities."""
    ctx.get_system(system_id)
    rows = ctx.query(
        "SELECT kri_name, date, value FROM kri_observations "
        "WHERE system_id = ? AND date >= ? AND date <= ? ORDER BY kri_name, date",
        (system_id, ctx.observation_start.isoformat(), ctx.as_of_date.isoformat()),
    )
    has_direct_vendor = bool(ctx.query(
        "SELECT target_id FROM dependencies WHERE source_id = ? "
        "AND relation = 'DEPENDS_ON' AND target_type = 'vendor'", (system_id,),
    ))
    series: list[MonitoredKri] = []
    for name in get_args(KriName):
        try:
            history = monitor_points([
                (date.fromisoformat(r["date"]), float(r["value"])) for r in rows if r["kri_name"] == name
            ])
        except ValueError as error:
            raise ToolFailure("data_unavailable", f"Invalid {name} history: {error}") from error
        recent = [p for p in history if p.date > window_start(ctx.as_of_date, 12)]
        scored = [p for p in recent if p.signal in SCORED_SIGNALS]
        flagged = sum(p.signal in FLAG_SIGNALS for p in scored)
        latest = history[-1] if history else None
        not_applicable = name == "vendor_incident_count" and not has_direct_vendor and latest is None
        series.append(MonitoredKri(
            kri_name=name,
            data_status="not_applicable" if not_applicable else "missing" if latest is None else (
                "current" if _month(latest.date) == _month(ctx.as_of_date) else "stale"
            ),
            applicability_basis=(
                "Atlas generator omits vendor_incident_count when no direct vendor dependency is recorded."
                if not_applicable else None
            ),
            latest=latest, scored_observations=len(scored), flagged_observations=flagged,
            flag_rate=flagged / len(scored) if scored else None,
            history=history,
            source_refs=[f"kri_observations:{system_id}:{name}:{p.date}" for p in history],
        ))
    return KriMonitoringResult(
        system_id=system_id, as_of_date=ctx.as_of_date, series=series,
        limitations=[
            "Illustrative one-sided rolling median/MAD rule, not approved risk appetite or a trained predictive model.",
            "Only earlier months enter each baseline. Scores above 3.5 flag an unusual increase.",
            "A zero MAD gives no z-score. Any increase over a flat baseline is a separate review signal.",
            "Missing, stale or gapped history is not evidence of low risk. No interpolation is used.",
            "Walk-forward flag rates measure alert workload, not precision, recall or future loss prediction.",
            "Synthetic data contain constructed drift. Seasonality, multiple testing and operational labels are not calibrated.",
        ],
    )
