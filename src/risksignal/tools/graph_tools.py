"""Dependency tool: wraps the graph queries; it builds no relationships of its own."""

from risksignal.graph.queries import (
    get_controls_for_system,
    get_related_systems,
    get_shared_vendors,
    get_supported_processes,
    get_system_dependencies,
)
from risksignal.tools.context import ToolContext, guarded
from risksignal.tools.schemas import DependenciesResult


@guarded("get_dependencies")
def get_dependencies(ctx: ToolContext, system_id: str) -> DependenciesResult:
    """Vendors, supported processes, controls and related systems of the system.

    Also returns the vendors shared with other systems, the systems it depends on (upstream)
    and the systems that depend on it (downstream), and vendors reached only indirectly. A
    "related" system shares a vendor or a business process; this is a shared exposure to
    investigate, not evidence that a problem in one system causes a problem in the other.
    The data are synthetic.
    """
    ctx.get_system(system_id)
    graph = ctx.graph
    dependencies = get_system_dependencies(graph, system_id)
    return DependenciesResult(
        tool_name="get_dependencies",
        system_id=system_id,
        vendors=dependencies.vendors,
        supported_processes=get_supported_processes(graph, system_id).processes,
        controls=get_controls_for_system(graph, system_id),
        shared_vendors=get_shared_vendors(graph, system_id).shared_vendors,
        related_systems=get_related_systems(graph, system_id).related_systems,
        upstream_systems=dependencies.upstream_systems,
        downstream_systems=dependencies.downstream_systems,
        indirect_vendors=dependencies.indirect_vendors,
    )
