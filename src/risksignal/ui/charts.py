"""Plotly figure builders for the UI. They only draw values the API returned."""

from typing import Any

import plotly.graph_objects as go

from risksignal.ui.formatting import label_for
from risksignal.ui.theme import (
    ACCENT,
    ACCENT_SECONDARY,
    BACKGROUND,
    BORDER_STRONG,
    DIVIDER,
    TEXT,
    TEXT_MUTED,
    style_figure,
)

NODE_COLORS = {"focus": TEXT, "vendor": ACCENT, "process": TEXT_MUTED, "related": BACKGROUND}
EDGE_COLORS = {"vendor": ACCENT_SECONDARY, "process": DIVIDER}
BASELINE_COLOR = ACCENT
STRESS_COLOR = ACCENT_SECONDARY
_FILLS = {BASELINE_COLOR: "rgba(76, 154, 255, 0.10)", STRESS_COLOR: "rgba(125, 184, 255, 0.18)"}
KRI_UNITS = {
    "failed_deployment_rate": "% of deployments",
    "system_downtime_minutes": "Minutes",
    "near_miss_count": "Count",
    "control_exception_count": "Count",
    "vendor_incident_count": "Count",
}


def kri_figure(series: dict[str, Any]) -> go.Figure:
    """Line chart of one KRI over the window, with the window mean as a dashed line."""
    points = series["observations"]
    figure = go.Figure(go.Scatter(
        x=[p["date"] for p in points], y=[p["value"] for p in points],
        mode="lines+markers", name=label_for(series["kri_name"]),
        line={"color": BASELINE_COLOR, "width": 1.5}, marker={"size": 5, "color": BASELINE_COLOR},
    ))
    figure.add_hline(y=series["window_mean"], line_dash="dot", line_color=ACCENT, line_width=1,
                     annotation_text="window mean", annotation_position="top left",
                     annotation_font={"color": ACCENT, "size": 12})
    return style_figure(figure, title={"text": label_for(series["kri_name"])}, height=300,
                        margin={"l": 8, "r": 8, "t": 56, "b": 8}, showlegend=False,
                        xaxis={"title": {"text": "Month"}},
                        yaxis={"title": {"text": KRI_UNITS.get(series["kri_name"], "Recorded value")},
                               "rangemode": "tozero"})


def _density(histogram: dict[str, Any]) -> tuple[list[float], list[float]]:
    """Bin edges and a step-plot height per bin: share of simulated years per unit of loss."""
    edges, counts = histogram["bin_edges"], histogram["counts"]
    total = sum(counts) + histogram["overflow_count"]
    heights = [c / (total * (edges[i + 1] - edges[i])) for i, c in enumerate(counts)]
    return edges, heights + [heights[-1]]


def distribution_figure(
    baseline_histogram: dict[str, Any], baseline_p95: float,
    stress_histogram: dict[str, Any] | None = None, stress_p95: float | None = None,
) -> go.Figure:
    """Annual loss distribution of the baseline (and the stress run, if given).

    Each histogram covers 0 to its own 99th percentile, and years above that are not drawn.
    Heights are densities (share of simulated years per unit of loss), so runs with different
    ranges can be compared. Dashed lines mark each P95.
    """
    figure = go.Figure()
    runs = [("Baseline", baseline_histogram, baseline_p95, BASELINE_COLOR)]
    if stress_histogram is not None and stress_p95 is not None:
        runs.append(("Stress", stress_histogram, stress_p95, STRESS_COLOR))
    for name, histogram, p95, color in runs:
        edges, heights = _density(histogram)
        figure.add_trace(go.Scatter(x=edges, y=heights, name=name, mode="lines",
                                    line={"color": color, "shape": "hv", "width": 1.5},
                                    fill="tozeroy", fillcolor=_FILLS[color]))
        figure.add_vline(x=p95, line_dash="dot", line_width=1, line_color=color, annotation_text=f"{name} P95",
                         annotation_position="top right", annotation_yanchor="top",
                         annotation_font={"color": color, "size": 12})
    return style_figure(
        figure,
        title={"text": "Simulated annual aggregate loss",
               "subtitle": {"text": "Illustrative model, synthetic data", "font": {"size": 12, "color": TEXT_MUTED}}},
        xaxis={"title": {"text": "Annual loss in synthetic monetary units (up to each run's P99)"}, "tickformat": "~s",
               "rangemode": "tozero"},
        yaxis={"title": {"text": "Density (share of simulated years)"}, "showticklabels": False},
        height=460, margin={"l": 8, "r": 8, "t": 80, "b": 8},
        legend={"orientation": "h", "y": -0.22, "x": 0},
    )


def _spread(count: int, height: float) -> list[float]:
    """Evenly spaced y positions, centred on zero, top to bottom."""
    if count == 1:
        return [0.0]
    return [height / 2 - i * height / (count - 1) for i in range(count)]


def dependency_layout(system_id: str, dependencies: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Node and edge data for the shared-exposure map around one system.

    Left: the system. Middle: its vendors and business processes. Right: related systems that
    share one of those vendors or processes, each linked to what it shares.
    """
    middle = ([("vendor", v["vendor_id"], f"{v['name']} ({v['vendor_id']})") for v in dependencies["vendors"]]
              + [("process", p["process_id"], f"{p['name']} ({p['process_id']})") for p in dependencies["supported_processes"]])
    related = dependencies["related_systems"]
    height = float(max(len(middle), len(related), 2))

    nodes: list[dict[str, Any]] = [{"key": f"system:{system_id}", "label": system_id, "kind": "focus", "x": 0.0, "y": 0.0,
                                    "hover": f"{system_id} (selected system)"}]
    for (kind, entity_id, label), y in zip(middle, _spread(len(middle), height)):
        nodes.append({"key": f"{kind}:{entity_id}", "label": label, "kind": kind, "x": 1.0, "y": y,
                      "hover": f"{kind.capitalize()}: {label}"})
    edges = [{"source": f"system:{system_id}", "target": f"{kind}:{entity_id}", "kind": kind} for kind, entity_id, _ in middle]
    for item, y in zip(related, _spread(len(related), height)):
        sys_id = item["system"]["system_id"]
        nodes.append({"key": f"related:{sys_id}", "label": sys_id, "kind": "related", "x": 2.0, "y": y,
                      "hover": "<br>".join(r["explanation"] for r in item["relationships"])})
        edges += [{"source": f"{r['kind'].replace('shared_', '')}:{r['entity_id']}", "target": f"related:{sys_id}",
                   "kind": r["kind"].replace("shared_", "")} for r in item["relationships"]]
    return {"nodes": nodes, "edges": edges}


def dependency_figure(system_id: str, dependencies: dict[str, Any]) -> go.Figure:
    """Readable shared-exposure map: system, its vendors and processes, and related systems."""
    layout = dependency_layout(system_id, dependencies)
    position = {n["key"]: (n["x"], n["y"]) for n in layout["nodes"]}
    figure = go.Figure()
    for kind in ("vendor", "process"):
        xs: list[float | None] = []
        ys: list[float | None] = []
        for edge in (e for e in layout["edges"] if e["kind"] == kind):
            (x0, y0), (x1, y1) = position[edge["source"]], position[edge["target"]]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        if xs:
            figure.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line={"color": EDGE_COLORS[kind], "width": 1},
                                        hoverinfo="skip", showlegend=False))
    names = {"focus": "Selected system", "vendor": "Vendor", "process": "Business process", "related": "Related system"}
    for kind in ("focus", "vendor", "process", "related"):
        group = [n for n in layout["nodes"] if n["kind"] == kind]
        if group:
            figure.add_trace(go.Scatter(
                x=[n["x"] for n in group], y=[n["y"] for n in group], mode="markers+text", name=names[kind],
                text=[n["label"] for n in group], textposition="middle right" if kind == "related" else "top center",
                textfont={"color": TEXT, "size": 12},
                hovertext=[n["hover"] for n in group], hoverinfo="text",
                marker={"size": 18 if kind == "focus" else 13, "color": NODE_COLORS[kind],
                        "line": {"color": BORDER_STRONG, "width": 1}},
            ))
    return style_figure(
        figure,
        title={"text": "Shared exposure map",
               "subtitle": {"text": "Synthetic data", "font": {"size": 12, "color": TEXT_MUTED}}},
        height=max(380, 60 * len({n["y"] for n in layout["nodes"]}) + 140),
        xaxis={"visible": False, "range": [-0.4, 3.4]}, yaxis={"visible": False},
        margin={"l": 8, "r": 8, "t": 72, "b": 8}, legend={"orientation": "h", "y": -0.05, "x": 0},
    )
