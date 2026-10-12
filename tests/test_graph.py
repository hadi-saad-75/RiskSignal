"""Tests for the dependency graph builder and queries."""

from pathlib import Path

import networkx as nx
import pandas as pd
import pytest
from pydantic import BaseModel

from risksignal.data.generator import generate_atlas_bank
from risksignal.data.storage import save_atlas_bank
from risksignal.graph.builder import build_graph, load_graph, node_key
from risksignal.graph.queries import (
    UnknownSystemError,
    get_controls_for_system,
    get_neighbor_summary,
    get_related_systems,
    get_shared_vendors,
    get_supported_processes,
    get_system_dependencies,
)

# A small hand-made bank (see docs/dependency_graph.md for the picture):
#
#   SYS_A --supports--> P1        SYS_A --vendor--> V1, V2      SYS_A --depends_on--> SYS_C
#   SYS_B --supports--> P1        SYS_B --vendor--> V1
#   SYS_C --supports--> P2        SYS_C --vendor--> V2          SYS_C --depends_on--> SYS_D
#   SYS_D --supports--> P2        SYS_D --vendor--> V3
#   SYS_E --supports--> P2        (no vendors, no controls)


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _system(system_id: str, process: str, criticality: str = "high") -> dict:
    return {"system_id": system_id, "name": f"System {system_id[-1]}", "description": "",
            "criticality": criticality, "primary_process_id": process}


def _dep(source: str, relation: str, target: str, target_type: str) -> dict:
    return {"source_id": source, "source_type": "system", "relation": relation,
            "target_id": target, "target_type": target_type}


def _control(control_id: str, system_id: str, status: str, review: str) -> dict:
    return {"control_id": control_id, "name": f"Control {control_id}", "description": "",
            "control_type": "preventive", "system_id": system_id,
            "last_review_date": review, "review_status": status}


def small_tables() -> dict[str, pd.DataFrame]:
    return {
        "systems": _frame([_system("SYS_A", "P1", "critical"), _system("SYS_B", "P1"),
                           _system("SYS_C", "P2"), _system("SYS_D", "P2"), _system("SYS_E", "P2", "low")]),
        "processes": _frame([{"process_id": "P1", "name": "Payments", "description": ""},
                             {"process_id": "P2", "name": "Reporting", "description": ""}]),
        "vendors": _frame([{"vendor_id": "V1", "name": "Alpha Vendor", "description": ""},
                           {"vendor_id": "V2", "name": "Beta Vendor", "description": ""},
                           {"vendor_id": "V3", "name": "Gamma Vendor", "description": ""}]),
        "controls": _frame([_control("C1", "SYS_A", "current", "2026-06-01"),
                            _control("C2", "SYS_A", "overdue", "2025-01-15"),
                            _control("C3", "SYS_B", "due", "2025-10-20")]),
        "dependencies": _frame([
            _dep("SYS_A", "SUPPORTS", "P1", "process"), _dep("SYS_B", "SUPPORTS", "P1", "process"),
            _dep("SYS_C", "SUPPORTS", "P2", "process"), _dep("SYS_D", "SUPPORTS", "P2", "process"),
            _dep("SYS_E", "SUPPORTS", "P2", "process"),
            _dep("SYS_A", "DEPENDS_ON", "V1", "vendor"), _dep("SYS_A", "DEPENDS_ON", "V2", "vendor"),
            _dep("SYS_B", "DEPENDS_ON", "V1", "vendor"), _dep("SYS_C", "DEPENDS_ON", "V2", "vendor"),
            _dep("SYS_D", "DEPENDS_ON", "V3", "vendor"),
            _dep("SYS_A", "DEPENDS_ON", "SYS_C", "system"), _dep("SYS_C", "DEPENDS_ON", "SYS_D", "system"),
        ]),
    }


@pytest.fixture(scope="module")
def graph() -> nx.DiGraph:
    return build_graph(small_tables())


# ----------------------------------------------------------------- building


def test_nodes_and_edges_are_built_from_the_tables(graph: nx.DiGraph) -> None:
    types = pd.Series([d["node_type"] for _, d in graph.nodes(data=True)]).value_counts().to_dict()
    assert types == {"system": 5, "process": 2, "vendor": 3, "control": 3}
    relations = pd.Series([d["relation"] for _, _, d in graph.edges(data=True)]).value_counts().to_dict()
    assert relations == {"SUPPORTS": 5, "DEPENDS_ON": 7, "PROTECTED_BY": 3}


def test_edge_directions_and_node_keys(graph: nx.DiGraph) -> None:
    assert graph.has_edge(node_key("system", "SYS_A"), node_key("process", "P1"))
    assert graph.has_edge(node_key("system", "SYS_A"), node_key("vendor", "V1"))
    assert graph.has_edge(node_key("system", "SYS_A"), node_key("control", "C1"))
    assert not graph.has_edge(node_key("process", "P1"), node_key("system", "SYS_A"))


def test_ids_of_different_types_cannot_collide() -> None:
    tables = small_tables()
    tables["vendors"].loc[0, "vendor_id"] = "SYS_A"  # same text as a system ID
    tables["dependencies"].loc[tables["dependencies"].target_id == "V1", "target_id"] = "SYS_A"
    built = build_graph(tables)
    assert node_key("vendor", "SYS_A") in built and node_key("system", "SYS_A") in built


def test_primary_process_is_marked_on_the_edge() -> None:
    tables = small_tables()
    tables["dependencies"] = pd.concat([tables["dependencies"], _frame([_dep("SYS_A", "SUPPORTS", "P2", "process")])])
    built = build_graph(tables)
    assert built.edges[node_key("system", "SYS_A"), node_key("process", "P1")]["primary"] is True
    assert built.edges[node_key("system", "SYS_A"), node_key("process", "P2")]["primary"] is False


def test_dependency_to_unknown_entity_is_rejected() -> None:
    tables = small_tables()
    tables["dependencies"] = pd.concat([tables["dependencies"], _frame([_dep("SYS_A", "DEPENDS_ON", "V99", "vendor")])])
    with pytest.raises(ValueError, match="V99"):
        build_graph(tables)


def test_control_for_unknown_system_and_missing_table_are_rejected() -> None:
    tables = small_tables()
    tables["controls"] = _frame([_control("C9", "NO_SYSTEM", "current", "2026-01-01")])
    with pytest.raises(ValueError, match="NO_SYSTEM"):
        build_graph(tables)
    del tables["vendors"]
    with pytest.raises(ValueError, match="vendors"):
        build_graph(tables)


# ----------------------------------------------------------------- shared vendors


def test_shared_vendors_are_detected(graph: nx.DiGraph) -> None:
    result = get_shared_vendors(graph, "SYS_A")
    assert [(s.vendor.vendor_id, [o.system_id for o in s.other_systems]) for s in result.shared_vendors] == [
        ("V1", ["SYS_B"]), ("V2", ["SYS_C"])]
    assert result.shared_vendors[0].vendor.name == "Alpha Vendor"


def test_vendor_used_by_one_system_only_is_not_shared(graph: nx.DiGraph) -> None:
    assert get_shared_vendors(graph, "SYS_D").shared_vendors == []  # V3 is used by SYS_D alone
    assert get_shared_vendors(graph, "SYS_E").shared_vendors == []  # no vendors at all


def test_sharing_is_symmetric(graph: nx.DiGraph) -> None:
    assert [o.system_id for o in get_shared_vendors(graph, "SYS_B").shared_vendors[0].other_systems] == ["SYS_A"]


# ----------------------------------------------------------------- related systems


def test_related_systems_explain_each_relationship(graph: nx.DiGraph) -> None:
    related = get_related_systems(graph, "SYS_A").related_systems
    assert [r.system.system_id for r in related] == ["SYS_B", "SYS_C"]  # most relationships first

    sys_b = related[0]
    assert [(r.kind, r.entity_id) for r in sys_b.relationships] == [("shared_vendor", "V1"), ("shared_process", "P1")]
    assert sys_b.relationships[0].explanation == "SYS_A and SYS_B both depend on vendor V1 (Alpha Vendor)."
    assert sys_b.relationships[1].explanation == "SYS_A and SYS_B both support business process P1 (Payments)."

    sys_c = related[1]
    assert [(r.kind, r.entity_id) for r in sys_c.relationships] == [("shared_vendor", "V2")]


def test_unrelated_systems_are_not_listed(graph: nx.DiGraph) -> None:
    ids = {r.system.system_id for r in get_related_systems(graph, "SYS_A").related_systems}
    assert ids == {"SYS_B", "SYS_C"}  # SYS_D (only an indirect dependency) and SYS_E share nothing with SYS_A


def test_related_through_process_only(graph: nx.DiGraph) -> None:
    related = get_related_systems(graph, "SYS_E").related_systems
    assert [r.system.system_id for r in related] == ["SYS_C", "SYS_D"]
    assert all([x.kind for x in r.relationships] == ["shared_process"] for r in related)


def test_related_is_symmetric(graph: nx.DiGraph) -> None:
    assert "SYS_A" in {r.system.system_id for r in get_related_systems(graph, "SYS_B").related_systems}


# ----------------------------------------------------------------- controls and processes


def test_controls_for_system(graph: nx.DiGraph) -> None:
    result = get_controls_for_system(graph, "SYS_A")
    assert [c.control_id for c in result.controls] == ["C1", "C2"]
    assert result.controls[1].review_status == "overdue"
    assert str(result.controls[1].last_review_date) == "2025-01-15"
    assert result.counts_by_review_status == {"current": 1, "overdue": 1}


def test_system_without_controls_returns_empty_result(graph: nx.DiGraph) -> None:
    result = get_controls_for_system(graph, "SYS_E")
    assert result.controls == [] and result.counts_by_review_status == {}


def test_supported_processes_flag_the_primary_one(graph: nx.DiGraph) -> None:
    processes = get_supported_processes(graph, "SYS_A").processes
    assert [(p.process_id, p.name, p.is_primary) for p in processes] == [("P1", "Payments", True)]


# ----------------------------------------------------------------- dependencies


def test_direct_and_indirect_dependencies(graph: nx.DiGraph) -> None:
    deps = get_system_dependencies(graph, "SYS_A")
    assert [v.vendor_id for v in deps.vendors] == ["V1", "V2"]
    assert [(u.system.system_id, u.hops, u.via_system_ids) for u in deps.upstream_systems] == [
        ("SYS_C", 1, []), ("SYS_D", 2, ["SYS_C"])]
    assert deps.downstream_systems == []
    # V3 is reached through SYS_D; V2 is already a direct vendor so it is not "indirect".
    assert [(v.vendor.vendor_id, v.via_system_id, v.hops) for v in deps.indirect_vendors] == [("V3", "SYS_D", 2)]


def test_downstream_systems_include_indirect_dependents(graph: nx.DiGraph) -> None:
    deps = get_system_dependencies(graph, "SYS_D")
    assert [(d.system.system_id, d.hops, d.via_system_ids) for d in deps.downstream_systems] == [
        ("SYS_C", 1, []), ("SYS_A", 2, ["SYS_C"])]
    assert deps.upstream_systems == []


def test_circular_dependencies_do_not_loop_forever() -> None:
    tables = small_tables()
    tables["dependencies"] = pd.concat([tables["dependencies"], _frame([_dep("SYS_D", "DEPENDS_ON", "SYS_A", "system")])])
    deps = get_system_dependencies(build_graph(tables), "SYS_A")
    assert [u.system.system_id for u in deps.upstream_systems] == ["SYS_C", "SYS_D"]


# ----------------------------------------------------------------- neighbour summary


def test_neighbor_summary_is_compact_and_consistent(graph: nx.DiGraph) -> None:
    summary = get_neighbor_summary(graph, "SYS_A")
    assert summary.system.system_id == "SYS_A" and summary.system.criticality == "critical"
    assert [p.process_id for p in summary.processes] == ["P1"]
    assert [v.vendor_id for v in summary.vendors] == ["V1", "V2"]
    assert [s.system_id for s in summary.upstream_systems] == ["SYS_C"]  # direct only
    assert summary.downstream_systems == []
    assert summary.controls.total == 2
    assert summary.controls.overdue_control_ids == ["C2"] and summary.controls.due_control_ids == []
    assert summary.shared_vendor_ids == ["V1", "V2"]
    assert summary.related_system_ids == ["SYS_B", "SYS_C"]


def test_neighbor_summary_of_an_isolated_system(graph: nx.DiGraph) -> None:
    summary = get_neighbor_summary(graph, "SYS_E")
    assert summary.vendors == [] and summary.upstream_systems == [] and summary.downstream_systems == []
    assert summary.controls.total == 0 and summary.shared_vendor_ids == []


# ----------------------------------------------------------------- unknown systems, output types


ALL_QUERIES = [get_system_dependencies, get_shared_vendors, get_related_systems,
               get_controls_for_system, get_supported_processes, get_neighbor_summary]


@pytest.mark.parametrize("query", ALL_QUERIES)
def test_unknown_system_raises_instead_of_returning_empty(graph: nx.DiGraph, query) -> None:
    with pytest.raises(UnknownSystemError, match="NO_SUCH_SYSTEM"):
        query(graph, "NO_SUCH_SYSTEM")


@pytest.mark.parametrize("query", ALL_QUERIES)
def test_ids_of_other_entity_types_are_not_systems(graph: nx.DiGraph, query) -> None:
    for wrong in ("V1", "P1", "C1"):
        with pytest.raises(UnknownSystemError):
            query(graph, wrong)


def test_unknown_system_error_suggests_close_matches(graph: nx.DiGraph) -> None:
    with pytest.raises(UnknownSystemError, match="Did you mean: SYS_A"):
        get_neighbor_summary(graph, "SYS_AA")


@pytest.mark.parametrize("query", ALL_QUERIES)
def test_results_are_pydantic_models_without_networkx_objects(graph: nx.DiGraph, query) -> None:
    result = query(graph, "SYS_A")
    assert isinstance(result, BaseModel)
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_queries_are_deterministic_and_do_not_modify_the_graph(graph: nx.DiGraph) -> None:
    before = (graph.number_of_nodes(), graph.number_of_edges())
    first = [q(graph, "SYS_A") for q in ALL_QUERIES]
    assert first == [q(graph, "SYS_A") for q in ALL_QUERIES]
    assert (graph.number_of_nodes(), graph.number_of_edges()) == before


# ----------------------------------------------------------------- Atlas Bank integration


@pytest.fixture(scope="module")
def atlas_graph(tmp_path_factory: pytest.TempPathFactory) -> nx.DiGraph:
    db_path = save_atlas_bank(generate_atlas_bank(), tmp_path_factory.mktemp("atlas_graph"))
    return load_graph(db_path)


def test_atlas_graph_matches_the_database_contents(atlas_graph: nx.DiGraph) -> None:
    counts = pd.Series([d["node_type"] for _, d in atlas_graph.nodes(data=True)]).value_counts().to_dict()
    assert counts == {"system": 20, "process": 10, "vendor": 8, "control": 40}
    relations = pd.Series([d["relation"] for _, _, d in atlas_graph.edges(data=True)]).value_counts().to_dict()
    assert relations == {"SUPPORTS": 30, "DEPENDS_ON": 47, "PROTECTED_BY": 40}


def test_payment_engines_are_related_through_the_shared_vendor(atlas_graph: nx.DiGraph) -> None:
    shared = get_shared_vendors(atlas_graph, "PAYMENT_ENGINE_01").shared_vendors
    v04 = next(s for s in shared if s.vendor.vendor_id == "V04")
    assert v04.vendor.name == "Keystone Payment Rails"
    assert [o.system_id for o in v04.other_systems] == ["PAYMENT_ENGINE_02"]

    related = {r.system.system_id: r for r in get_related_systems(atlas_graph, "PAYMENT_ENGINE_01").related_systems}
    relationships = related["PAYMENT_ENGINE_02"].relationships
    assert [(r.kind, r.entity_id) for r in relationships] == [("shared_vendor", "V04")]
    assert "Keystone Payment Rails" in relationships[0].explanation
    reverse = get_related_systems(atlas_graph, "PAYMENT_ENGINE_02").related_systems
    assert "PAYMENT_ENGINE_01" in {r.system.system_id for r in reverse}  # the link is symmetric


def test_focal_system_neighbourhood_in_atlas_bank(atlas_graph: nx.DiGraph) -> None:
    summary = get_neighbor_summary(atlas_graph, "PAYMENT_ENGINE_01")
    assert [p.name for p in summary.processes] == ["International Payments"]
    assert {"V04", "V02"} == {v.vendor_id for v in summary.vendors}
    assert summary.controls.total == 4 and len(summary.controls.overdue_control_ids) == 1
    assert "PAYMENT_ENGINE_02" in summary.related_system_ids


def test_atlas_indirect_vendor_exposure_is_found(atlas_graph: nx.DiGraph) -> None:
    deps = get_system_dependencies(atlas_graph, "PAYMENT_ENGINE_01")
    indirect = {v.vendor.vendor_id: v for v in deps.indirect_vendors}
    assert "V03" in indirect and indirect["V03"].via_system_id == "SSO_GATEWAY_01"  # identity vendor, via SSO
    assert not {"V04", "V02"} & set(indirect)  # direct vendors are never listed as indirect


def test_every_atlas_system_can_be_queried(atlas_graph: nx.DiGraph) -> None:
    system_ids = [d["entity_id"] for _, d in atlas_graph.nodes(data=True) if d["node_type"] == "system"]
    for system_id in system_ids:
        assert get_neighbor_summary(atlas_graph, system_id).system.system_id == system_id


def test_graph_package_does_not_depend_on_llm_api_or_ui() -> None:
    package = Path(__file__).resolve().parents[1] / "src" / "risksignal" / "graph"
    forbidden = ("anthropic", "risksignal.agent", "risksignal.api", "risksignal.ui", "risksignal.tools",
                 "risksignal.stochastic", "fastapi", "streamlit")
    for source in package.glob("*.py"):
        imports = [l for l in source.read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from "))]
        assert not [i for i in imports if any(name in i for name in forbidden)], source.name
