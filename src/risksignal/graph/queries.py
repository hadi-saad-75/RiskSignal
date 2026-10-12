"""Read-only queries on the dependency graph. Each returns a structured pydantic object.

All functions take the graph as first argument and a ``system_id``. An unknown system raises
``UnknownSystemError`` (never an empty result), so a typo cannot be mistaken for "no risk".
Results are sorted, so they are deterministic.

Plain English
-------------
The graph lets us follow connections: which vendors a system uses, which other systems use
the same vendors, which processes it supports, and which controls protect it. "Related"
means structurally linked (a common vendor or process). It does not mean a failure in one
system causes a failure in the other.
"""

import difflib

import networkx as nx

from risksignal.graph.builder import node_key
from risksignal.graph.schemas import (
    ControlRef,
    ControlStatusSummary,
    IndirectVendor,
    NeighborSummary,
    ProcessRef,
    RelatedSystem,
    RelatedSystems,
    Relationship,
    SharedVendor,
    SharedVendors,
    SupportedProcesses,
    SystemControls,
    SystemDependencies,
    SystemLink,
    SystemRef,
    VendorRef,
)


class UnknownSystemError(ValueError):
    """Raised when a system_id is not a system in the graph."""


# --------------------------------------------------------------------------- helpers


def _system_key(graph: nx.DiGraph, system_id: str) -> str:
    key = node_key("system", system_id)
    if key not in graph:
        known = [n["entity_id"] for _, n in graph.nodes(data=True) if n["node_type"] == "system"]
        hints = difflib.get_close_matches(str(system_id), known, n=3, cutoff=0.6)
        suffix = f" Did you mean: {', '.join(hints)}?" if hints else ""
        raise UnknownSystemError(f"Unknown system '{system_id}'.{suffix}")
    return key


def _id(graph: nx.DiGraph, key: str) -> str:
    return graph.nodes[key]["entity_id"]


def _out(graph: nx.DiGraph, key: str, relation: str, node_type: str) -> list[str]:
    """Keys of nodes this node points to via ``relation``, sorted by ID."""
    found = [t for _, t, d in graph.out_edges(key, data=True)
             if d["relation"] == relation and graph.nodes[t]["node_type"] == node_type]
    return sorted(found, key=lambda k: _id(graph, k))


def _in(graph: nx.DiGraph, key: str, relation: str, node_type: str) -> list[str]:
    """Keys of nodes pointing to this node via ``relation``, sorted by ID."""
    found = [s for s, _, d in graph.in_edges(key, data=True)
             if d["relation"] == relation and graph.nodes[s]["node_type"] == node_type]
    return sorted(found, key=lambda k: _id(graph, k))


def _system_ref(graph: nx.DiGraph, key: str) -> SystemRef:
    node = graph.nodes[key]
    return SystemRef(system_id=node["entity_id"], name=node["name"], criticality=node["criticality"])


def _vendor_ref(graph: nx.DiGraph, key: str) -> VendorRef:
    node = graph.nodes[key]
    return VendorRef(vendor_id=node["entity_id"], name=node["name"])


def _process_ref(graph: nx.DiGraph, system: str, process: str) -> ProcessRef:
    node = graph.nodes[process]
    return ProcessRef(
        process_id=node["entity_id"], name=node["name"],
        is_primary=bool(graph.edges[system, process].get("primary", False)),
    )


def _control_ref(graph: nx.DiGraph, key: str) -> ControlRef:
    node = graph.nodes[key]
    return ControlRef(
        control_id=node["entity_id"], name=node["name"], control_type=node["control_type"],
        last_review_date=node["last_review_date"], review_status=node["review_status"],
    )


def _system_dependency_graph(graph: nx.DiGraph) -> nx.DiGraph:
    """Only the system-to-system DEPENDS_ON edges (all systems included as nodes)."""
    sub = nx.DiGraph()
    sub.add_nodes_from(k for k, n in graph.nodes(data=True) if n["node_type"] == "system")
    sub.add_edges_from(
        (u, v) for u, v, d in graph.edges(data=True)
        if d["relation"] == "DEPENDS_ON"
        and graph.nodes[u]["node_type"] == "system" and graph.nodes[v]["node_type"] == "system"
    )
    return sub


def _links(graph: nx.DiGraph, systems_graph: nx.DiGraph, key: str) -> list[SystemLink]:
    """Systems reachable from ``key`` in ``systems_graph``, nearest first (shortest chains)."""
    paths = nx.single_source_shortest_path(systems_graph, key)
    links = [
        SystemLink(
            system=_system_ref(graph, path[-1]), hops=len(path) - 1,
            via_system_ids=[_id(graph, k) for k in path[1:-1]],
        )
        for target, path in paths.items() if target != key
    ]
    return sorted(links, key=lambda link: (link.hops, link.system.system_id))


def _control_status_counts(controls: list[ControlRef]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for control in controls:
        counts[control.review_status] = counts.get(control.review_status, 0) + 1
    return dict(sorted(counts.items()))


# --------------------------------------------------------------------------- queries


def get_system_dependencies(graph: nx.DiGraph, system_id: str) -> SystemDependencies:
    """Direct vendors, upstream and downstream systems, and vendors reached indirectly.

    *Upstream* systems are those this system depends on (directly or through a chain).
    *Downstream* systems are those that depend on it. *Indirect vendors* are vendors used by
    upstream systems but not directly by this system, each with the nearest system through
    which it is reached.
    """
    key = _system_key(graph, system_id)
    systems_graph = _system_dependency_graph(graph)
    direct = set(_out(graph, key, "DEPENDS_ON", "vendor"))
    upstream = _links(graph, systems_graph, key)
    downstream = _links(graph, systems_graph.reverse(copy=False), key)

    indirect: list[IndirectVendor] = []
    seen = set(direct)
    for link in upstream:
        for vendor in _out(graph, node_key("system", link.system.system_id), "DEPENDS_ON", "vendor"):
            if vendor not in seen:
                seen.add(vendor)
                indirect.append(IndirectVendor(
                    vendor=_vendor_ref(graph, vendor), via_system_id=link.system.system_id, hops=link.hops))
    return SystemDependencies(
        system_id=system_id,
        vendors=[_vendor_ref(graph, v) for v in sorted(direct, key=lambda k: _id(graph, k))],
        upstream_systems=upstream,
        downstream_systems=downstream,
        indirect_vendors=sorted(indirect, key=lambda v: v.vendor.vendor_id),
    )


def get_shared_vendors(graph: nx.DiGraph, system_id: str) -> SharedVendors:
    """Direct vendors of the system that at least one other system also uses directly."""
    key = _system_key(graph, system_id)
    shared = []
    for vendor in _out(graph, key, "DEPENDS_ON", "vendor"):
        others = [s for s in _in(graph, vendor, "DEPENDS_ON", "system") if s != key]
        if others:
            shared.append(SharedVendor(
                vendor=_vendor_ref(graph, vendor), other_systems=[_system_ref(graph, s) for s in others]))
    return SharedVendors(system_id=system_id, shared_vendors=shared)


def get_related_systems(graph: nx.DiGraph, system_id: str) -> RelatedSystems:
    """Systems linked through a shared vendor or a shared business process, with explanations.

    Sorted by number of relationships (most first), then system ID.
    """
    key = _system_key(graph, system_id)
    found: dict[str, list[Relationship]] = {}
    for vendor in _out(graph, key, "DEPENDS_ON", "vendor"):
        node = graph.nodes[vendor]
        for other in (s for s in _in(graph, vendor, "DEPENDS_ON", "system") if s != key):
            found.setdefault(other, []).append(Relationship(
                kind="shared_vendor", entity_id=node["entity_id"], entity_name=node["name"],
                explanation=(f"{system_id} and {_id(graph, other)} both depend on vendor "
                             f"{node['entity_id']} ({node['name']})."),
            ))
    for process in _out(graph, key, "SUPPORTS", "process"):
        node = graph.nodes[process]
        for other in (s for s in _in(graph, process, "SUPPORTS", "system") if s != key):
            found.setdefault(other, []).append(Relationship(
                kind="shared_process", entity_id=node["entity_id"], entity_name=node["name"],
                explanation=(f"{system_id} and {_id(graph, other)} both support business process "
                             f"{node['entity_id']} ({node['name']})."),
            ))
    ordered = sorted(found, key=lambda k: (-len(found[k]), _id(graph, k)))
    return RelatedSystems(
        system_id=system_id,
        related_systems=[RelatedSystem(system=_system_ref(graph, k), relationships=found[k]) for k in ordered],
    )


def get_controls_for_system(graph: nx.DiGraph, system_id: str) -> SystemControls:
    """Controls attached to the system (PROTECTED_BY), with counts by review status."""
    key = _system_key(graph, system_id)
    controls = [_control_ref(graph, c) for c in _out(graph, key, "PROTECTED_BY", "control")]
    return SystemControls(system_id=system_id, controls=controls, counts_by_review_status=_control_status_counts(controls))


def get_supported_processes(graph: nx.DiGraph, system_id: str) -> SupportedProcesses:
    """Business processes the system supports. The primary process is flagged."""
    key = _system_key(graph, system_id)
    return SupportedProcesses(
        system_id=system_id,
        processes=[_process_ref(graph, key, p) for p in _out(graph, key, "SUPPORTS", "process")],
    )


def get_neighbor_summary(graph: nx.DiGraph, system_id: str) -> NeighborSummary:
    """Compact overview of everything directly connected to the system."""
    key = _system_key(graph, system_id)
    controls = get_controls_for_system(graph, system_id).controls
    return NeighborSummary(
        system=_system_ref(graph, key),
        processes=get_supported_processes(graph, system_id).processes,
        vendors=[_vendor_ref(graph, v) for v in _out(graph, key, "DEPENDS_ON", "vendor")],
        upstream_systems=[_system_ref(graph, s) for s in _out(graph, key, "DEPENDS_ON", "system")],
        downstream_systems=[_system_ref(graph, s) for s in _in(graph, key, "DEPENDS_ON", "system")],
        controls=ControlStatusSummary(
            total=len(controls),
            counts_by_review_status=_control_status_counts(controls),
            overdue_control_ids=[c.control_id for c in controls if c.review_status == "overdue"],
            due_control_ids=[c.control_id for c in controls if c.review_status == "due"],
        ),
        shared_vendor_ids=[s.vendor.vendor_id for s in get_shared_vendors(graph, system_id).shared_vendors],
        related_system_ids=[r.system.system_id for r in get_related_systems(graph, system_id).related_systems],
    )
