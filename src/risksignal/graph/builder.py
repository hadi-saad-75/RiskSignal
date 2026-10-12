"""Build the dependency graph from the Atlas Bank tables.

Plain English
-------------
The graph is a map. Each system, business process, vendor and control is a dot (a *node*).
A line between two dots (an *edge*) records one relationship, such as "this system supports
that process". Everything on the map is read from the database tables, nothing is typed in
by hand here.

Structure
---------
Nodes (key = ``"<type>:<id>"`` so IDs of different types can never collide):

    system, process, vendor, control

Directed edges, each with a ``relation`` attribute:

    system  --SUPPORTS-->     process
    system  --DEPENDS_ON-->   vendor
    system  --DEPENDS_ON-->   system
    system  --PROTECTED_BY--> control

SUPPORTS and DEPENDS_ON come from the ``dependencies`` table. PROTECTED_BY comes from the
``system_id`` column of the ``controls`` table. Incidents are intentionally not nodes: the
graph holds structure only, and incident history is retrieved from the data tables.

The synthetic graph demonstrates reasoning mechanics only. A real bank graph would need
verified configuration, service, process and vendor data.
"""

from collections.abc import Mapping
from pathlib import Path

import networkx as nx
import pandas as pd

from risksignal.data.storage import DB_FILENAME, DEFAULT_DATA_DIR, read_table

REQUIRED_TABLES = ("systems", "processes", "vendors", "controls", "dependencies")
_NODE_TABLES = {"system": "systems", "process": "processes", "vendor": "vendors", "control": "controls"}
_NODE_ID_COLUMN = {"system": "system_id", "process": "process_id", "vendor": "vendor_id", "control": "control_id"}


def node_key(node_type: str, entity_id: str) -> str:
    """Graph key for an entity, for example ``system:PAYMENT_ENGINE_01``."""
    return f"{node_type}:{entity_id}"


def _add_nodes(graph: nx.DiGraph, node_type: str, table: pd.DataFrame) -> None:
    id_column = _NODE_ID_COLUMN[node_type]
    for row in table.to_dict("records"):
        entity_id = row[id_column]
        attributes = {k: v for k, v in row.items() if k != id_column}
        graph.add_node(node_key(node_type, entity_id), node_type=node_type, entity_id=entity_id, **attributes)


def _require(graph: nx.DiGraph, node_type: str, entity_id: str, context: str) -> str:
    key = node_key(node_type, entity_id)
    if key not in graph:
        raise ValueError(f"{context} refers to unknown {node_type} '{entity_id}'")
    return key


def _add_dependency_edges(graph: nx.DiGraph, dependencies: pd.DataFrame) -> None:
    for row in dependencies.to_dict("records"):
        source = _require(graph, row["source_type"], row["source_id"], "dependency source")
        target = _require(graph, row["target_type"], row["target_id"], "dependency target")
        attributes = {"relation": row["relation"]}
        if row["relation"] == "SUPPORTS":
            attributes["primary"] = graph.nodes[source].get("primary_process_id") == row["target_id"]
        graph.add_edge(source, target, **attributes)


def _add_control_edges(graph: nx.DiGraph, controls: pd.DataFrame) -> None:
    for row in controls.to_dict("records"):
        system = _require(graph, "system", row["system_id"], f"control {row['control_id']}")
        graph.add_edge(system, node_key("control", row["control_id"]), relation="PROTECTED_BY")


def build_graph(tables: Mapping[str, pd.DataFrame]) -> nx.DiGraph:
    """Build the graph from tables named ``systems``, ``processes``, ``vendors``,
    ``controls`` and ``dependencies`` (same columns as the SQLite database).

    Raises ``ValueError`` if a table is missing or a row refers to an entity that does not exist.
    """
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    if missing:
        raise ValueError(f"missing tables: {missing}")
    graph = nx.DiGraph()
    for node_type, table_name in _NODE_TABLES.items():
        _add_nodes(graph, node_type, tables[table_name])
    _add_dependency_edges(graph, tables["dependencies"])
    _add_control_edges(graph, tables["controls"])
    return graph


def load_graph(db_path: Path = DEFAULT_DATA_DIR / DB_FILENAME) -> nx.DiGraph:
    """Build the graph from the Atlas Bank SQLite database."""
    return build_graph({name: read_table(name, db_path) for name in REQUIRED_TABLES})
