"""Pydantic schemas and integrity validation for the synthetic Atlas Bank dataset.

Every row type is a small frozen model. ``AtlasBankDataset`` groups one list of rows
per table, and ``validate_dataset`` checks cross-table rules (unique IDs, foreign keys,
dependency endpoints) that a single row cannot check on its own.

All data described here are synthetic. See docs/limitations.md.
"""

import datetime as dt
from collections import Counter
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Criticality = Literal["low", "medium", "high", "critical"]
ControlType = Literal["preventive", "detective", "corrective"]
ReviewStatus = Literal["current", "due", "overdue"]
IncidentCategory = Literal[
    "technology_failure",
    "process_failure",
    "third_party_failure",
    "human_error",
    "cyber_event",
]
Severity = Literal["low", "medium", "high", "critical"]
KriName = Literal[
    "failed_deployment_rate",
    "system_downtime_minutes",
    "near_miss_count",
    "control_exception_count",
    "vendor_incident_count",
]
EntityType = Literal["system", "process", "vendor"]
Relation = Literal["SUPPORTS", "DEPENDS_ON"]


class _Row(BaseModel):
    """Base class for one table row: immutable, no unexpected fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class Process(_Row):
    process_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str


class Vendor(_Row):
    vendor_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str


class System(_Row):
    system_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    criticality: Criticality
    primary_process_id: str = Field(min_length=1)


class Control(_Row):
    control_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    control_type: ControlType
    system_id: str = Field(min_length=1)
    last_review_date: dt.date
    review_status: ReviewStatus


class Incident(_Row):
    incident_id: str = Field(min_length=1)
    date: dt.date
    system_id: str = Field(min_length=1)
    category: IncidentCategory
    description: str = Field(min_length=1)
    financial_loss: float = Field(ge=0)
    severity: Severity


class KriObservation(_Row):
    date: dt.date
    system_id: str = Field(min_length=1)
    kri_name: KriName
    value: float = Field(ge=0)


class Dependency(_Row):
    """A directed relationship: ``source`` --relation--> ``target``.

    SYSTEM SUPPORTS PROCESS, SYSTEM DEPENDS_ON VENDOR, SYSTEM DEPENDS_ON SYSTEM.
    """

    source_id: str = Field(min_length=1)
    source_type: EntityType
    relation: Relation
    target_id: str = Field(min_length=1)
    target_type: EntityType

    @model_validator(mode="after")
    def _check_relation_types(self) -> Self:
        allowed_targets = {"SUPPORTS": ("process",), "DEPENDS_ON": ("vendor", "system")}
        if self.source_type != "system":
            raise ValueError("dependency source must be a system")
        if self.target_type not in allowed_targets[self.relation]:
            raise ValueError(f"{self.relation} cannot point to a {self.target_type}")
        if self.source_id == self.target_id and self.target_type == "system":
            raise ValueError("a system cannot depend on itself")
        return self


class AtlasBankDataset(BaseModel):
    """All Atlas Bank tables. Field names are the table names."""

    systems: list[System]
    processes: list[Process]
    vendors: list[Vendor]
    controls: list[Control]
    incidents: list[Incident]
    kri_observations: list[KriObservation]
    dependencies: list[Dependency]


# Parent tables come before the tables that reference them.
TABLE_MODELS: dict[str, type[_Row]] = {
    "processes": Process,
    "vendors": Vendor,
    "systems": System,
    "controls": Control,
    "incidents": Incident,
    "kri_observations": KriObservation,
    "dependencies": Dependency,
}


class DatasetValidationError(ValueError):
    """Raised when a dataset breaks an integrity rule. Lists every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def _duplicates(label: str, keys: list[object]) -> list[str]:
    return [f"duplicate {label}: {key}" for key, n in Counter(keys).items() if n > 1]


def _check_unique_keys(ds: AtlasBankDataset) -> list[str]:
    problems: list[str] = []
    problems += _duplicates("process_id", [p.process_id for p in ds.processes])
    problems += _duplicates("vendor_id", [v.vendor_id for v in ds.vendors])
    problems += _duplicates("system_id", [s.system_id for s in ds.systems])
    problems += _duplicates("control_id", [c.control_id for c in ds.controls])
    problems += _duplicates("incident_id", [i.incident_id for i in ds.incidents])
    problems += _duplicates(
        "KRI observation", [(k.date, k.system_id, k.kri_name) for k in ds.kri_observations]
    )
    problems += _duplicates(
        "dependency", [(d.source_id, d.relation, d.target_id) for d in ds.dependencies]
    )
    return problems


def _missing(label: str, referenced: list[str], valid: set[str]) -> list[str]:
    return [f"{label} references unknown id: {ref}" for ref in sorted(set(referenced) - valid)]


def _check_foreign_keys(ds: AtlasBankDataset) -> list[str]:
    system_ids = {s.system_id for s in ds.systems}
    process_ids = {p.process_id for p in ds.processes}
    problems: list[str] = []
    problems += _missing("system.primary_process_id", [s.primary_process_id for s in ds.systems], process_ids)
    problems += _missing("control.system_id", [c.system_id for c in ds.controls], system_ids)
    problems += _missing("incident.system_id", [i.system_id for i in ds.incidents], system_ids)
    problems += _missing("kri.system_id", [k.system_id for k in ds.kri_observations], system_ids)
    return problems


def _check_dependencies(ds: AtlasBankDataset) -> list[str]:
    ids_by_type = {
        "system": {s.system_id for s in ds.systems},
        "process": {p.process_id for p in ds.processes},
        "vendor": {v.vendor_id for v in ds.vendors},
    }
    problems: list[str] = []
    for dep in ds.dependencies:
        if dep.source_id not in ids_by_type[dep.source_type]:
            problems.append(f"dependency source not found: {dep.source_type} {dep.source_id}")
        if dep.target_id not in ids_by_type[dep.target_type]:
            problems.append(f"dependency target not found: {dep.target_type} {dep.target_id}")
    supported = {(d.source_id, d.target_id) for d in ds.dependencies if d.relation == "SUPPORTS"}
    for system in ds.systems:
        if (system.system_id, system.primary_process_id) not in supported:
            problems.append(f"{system.system_id} has no SUPPORTS link to its primary process")
    return problems


def _check_dates(ds: AtlasBankDataset, max_date: dt.date) -> list[str]:
    problems = [f"incident {i.incident_id} dated after {max_date}" for i in ds.incidents if i.date > max_date]
    problems += [
        f"KRI observation for {k.system_id} dated after {max_date}"
        for k in ds.kri_observations
        if k.date > max_date
    ]
    return problems


def validate_dataset(dataset: AtlasBankDataset, max_date: dt.date | None = None) -> None:
    """Check cross-table integrity; raise ``DatasetValidationError`` listing all problems.

    Per-row rules (non-negative losses, valid calendar dates, allowed categories) are
    enforced by the row schemas themselves. If ``max_date`` is given, no incident or
    KRI observation may be dated after it.
    """
    problems = _check_unique_keys(dataset) + _check_foreign_keys(dataset) + _check_dependencies(dataset)
    if max_date is not None:
        problems += _check_dates(dataset, max_date)
    if problems:
        raise DatasetValidationError(problems)
