"""Pydantic result types for dependency graph queries.

Queries never return NetworkX objects, only these small structured models, so results
can be passed to the tool layer, the agent and the API unchanged.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SystemRef(_Model):
    system_id: str
    name: str
    criticality: str


class ProcessRef(_Model):
    process_id: str
    name: str
    is_primary: bool = False


class VendorRef(_Model):
    vendor_id: str
    name: str


class ControlRef(_Model):
    control_id: str
    name: str
    control_type: str
    last_review_date: dt.date
    review_status: str


# --------------------------------------------------------------------------- dependencies


class SystemLink(_Model):
    """Another system reachable by following system-to-system DEPENDS_ON edges.

    ``hops`` is the length of the shortest chain (1 = direct). ``via_system_ids`` lists the
    systems in between, in order, starting next to the queried system. It is empty for direct links.
    """

    system: SystemRef
    hops: int
    via_system_ids: list[str]


class IndirectVendor(_Model):
    """A vendor the system does not use directly but reaches through an upstream system."""

    vendor: VendorRef
    via_system_id: str
    hops: int


class SystemDependencies(_Model):
    """What a system depends on (upstream) and what depends on it (downstream)."""

    system_id: str
    vendors: list[VendorRef]
    upstream_systems: list[SystemLink]
    downstream_systems: list[SystemLink]
    indirect_vendors: list[IndirectVendor]


# --------------------------------------------------------------------------- shared vendors


class SharedVendor(_Model):
    vendor: VendorRef
    other_systems: list[SystemRef]


class SharedVendors(_Model):
    """Direct vendors of a system that at least one other system also depends on directly."""

    system_id: str
    shared_vendors: list[SharedVendor]


# --------------------------------------------------------------------------- related systems


class Relationship(_Model):
    kind: Literal["shared_vendor", "shared_process"]
    entity_id: str
    entity_name: str
    explanation: str


class RelatedSystem(_Model):
    system: SystemRef
    relationships: list[Relationship]


class RelatedSystems(_Model):
    """Systems linked to the queried system through a common vendor or business process.

    A relationship means a *shared structural exposure* worth investigating. It does not
    mean that a problem in one system causes a problem in the other.
    """

    system_id: str
    related_systems: list[RelatedSystem]


# --------------------------------------------------------------------------- controls, processes


class SystemControls(_Model):
    system_id: str
    controls: list[ControlRef]
    counts_by_review_status: dict[str, int]


class SupportedProcesses(_Model):
    system_id: str
    processes: list[ProcessRef]


# --------------------------------------------------------------------------- summary


class ControlStatusSummary(_Model):
    total: int
    counts_by_review_status: dict[str, int]
    overdue_control_ids: list[str]
    due_control_ids: list[str]


class NeighborSummary(_Model):
    """Compact overview of everything directly connected to one system."""

    system: SystemRef
    processes: list[ProcessRef]
    vendors: list[VendorRef]
    upstream_systems: list[SystemRef]
    downstream_systems: list[SystemRef]
    controls: ControlStatusSummary
    shared_vendor_ids: list[str]
    related_system_ids: list[str]
