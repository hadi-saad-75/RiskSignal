"""Tests for the synthetic Atlas Bank generator and schemas."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from risksignal.data.generator import (
    DATA_END,
    DATA_START,
    DEFAULT_SEED,
    FOCAL_SYSTEM_ID,
    generate_atlas_bank,
    review_status_for,
    severity_for_loss,
)
from risksignal.data.schemas import (
    AtlasBankDataset,
    Dependency,
    DatasetValidationError,
    Incident,
    System,
    TABLE_MODELS,
    validate_dataset,
)


@pytest.fixture(scope="module")
def dataset() -> AtlasBankDataset:
    return generate_atlas_bank(DEFAULT_SEED)


# ----------------------------------------------------------------- size and shape


def test_entity_counts_are_roughly_as_specified(dataset: AtlasBankDataset) -> None:
    assert len(dataset.systems) == 20
    assert len(dataset.processes) == 10
    assert len(dataset.vendors) == 8
    assert len(dataset.controls) == 40
    assert 270 <= len(dataset.incidents) <= 340


def test_required_entities_exist(dataset: AtlasBankDataset) -> None:
    system_ids = {s.system_id for s in dataset.systems}
    process_names = {p.name for p in dataset.processes}
    assert {"PAYMENT_ENGINE_01", "PAYMENT_ENGINE_02"} <= system_ids
    assert {
        "International Payments",
        "Domestic Payments",
        "Trade Settlement",
        "Client Onboarding",
        "Identity and Access Management",
    } <= process_names


def test_incident_fields_have_no_prediction_label() -> None:
    assert list(Incident.model_fields) == [
        "incident_id", "date", "system_id", "category", "description", "financial_loss", "severity",
    ]
    all_fields = {f for model in TABLE_MODELS.values() for f in model.model_fields}
    forbidden = ("prob", "label", "predict", "future", "ml_")
    assert not [f for f in all_fields if any(word in f for word in forbidden)]


def test_incident_dates_are_within_window(dataset: AtlasBankDataset) -> None:
    assert all(DATA_START <= i.date <= DATA_END for i in dataset.incidents)
    span_years = (max(i.date for i in dataset.incidents) - min(i.date for i in dataset.incidents)).days / 365.25
    assert 4.5 <= span_years <= 5.0


def test_kri_series_are_monthly_and_complete(dataset: AtlasBankDataset) -> None:
    dates_by_series: dict[tuple[str, str], list[date]] = {}
    for obs in dataset.kri_observations:
        dates_by_series.setdefault((obs.system_id, obs.kri_name), []).append(obs.date)
    assert dates_by_series
    for dates in dates_by_series.values():
        assert len(dates) == 60
        assert dates == sorted(dates)
        assert len({(d.year, d.month) for d in dates}) == 60
    kri_names = {name for _, name in dates_by_series}
    assert kri_names == {
        "failed_deployment_rate", "system_downtime_minutes", "near_miss_count",
        "control_exception_count", "vendor_incident_count",
    }


def test_vendor_kri_only_for_systems_with_vendors(dataset: AtlasBankDataset) -> None:
    with_vendor = {d.source_id for d in dataset.dependencies if d.target_type == "vendor"}
    vendor_kri_systems = {k.system_id for k in dataset.kri_observations if k.kri_name == "vendor_incident_count"}
    assert vendor_kri_systems == with_vendor


def test_severity_labels_match_loss_thresholds(dataset: AtlasBankDataset) -> None:
    assert all(i.severity == severity_for_loss(i.financial_loss) for i in dataset.incidents)
    assert {i.severity for i in dataset.incidents} >= {"low", "medium", "high"}


def test_control_review_status_matches_review_date(dataset: AtlasBankDataset) -> None:
    assert all(c.review_status == review_status_for(c.last_review_date) for c in dataset.controls)
    assert {c.review_status for c in dataset.controls} == {"current", "due", "overdue"}


def test_review_status_boundaries() -> None:
    assert review_status_for(DATA_END - timedelta(days=365)) == "due"
    assert review_status_for(DATA_END - timedelta(days=366)) == "overdue"
    assert review_status_for(DATA_END - timedelta(days=305)) == "due"
    assert review_status_for(DATA_END - timedelta(days=304)) == "current"


# ----------------------------------------------------------------- reproducibility


def test_same_seed_gives_identical_dataset(dataset: AtlasBankDataset) -> None:
    assert generate_atlas_bank(DEFAULT_SEED) == dataset


def test_different_seed_changes_random_parts_only(dataset: AtlasBankDataset) -> None:
    other = generate_atlas_bank(DEFAULT_SEED + 1)
    assert other.incidents != dataset.incidents
    assert other.kri_observations != dataset.kri_observations
    assert other.systems == dataset.systems
    assert other.dependencies == dataset.dependencies


# ----------------------------------------------------------------- referential integrity


def test_generated_dataset_passes_validation(dataset: AtlasBankDataset) -> None:
    validate_dataset(dataset, max_date=DATA_END)


def test_validation_detects_duplicate_ids(dataset: AtlasBankDataset) -> None:
    broken = dataset.model_copy(update={"vendors": dataset.vendors + [dataset.vendors[0]]})
    with pytest.raises(DatasetValidationError, match="duplicate vendor_id"):
        validate_dataset(broken)


def test_validation_detects_unknown_system_in_incident(dataset: AtlasBankDataset) -> None:
    template = dataset.incidents[0]
    bad = Incident(**{**template.model_dump(), "incident_id": "INC9999", "system_id": "NO_SUCH_SYSTEM"})
    broken = dataset.model_copy(update={"incidents": dataset.incidents + [bad]})
    with pytest.raises(DatasetValidationError, match="NO_SUCH_SYSTEM"):
        validate_dataset(broken)


def test_validation_detects_unknown_primary_process(dataset: AtlasBankDataset) -> None:
    bad = System(**{**dataset.systems[0].model_dump(), "primary_process_id": "P99"})
    broken = dataset.model_copy(update={"systems": [bad] + dataset.systems[1:]})
    with pytest.raises(DatasetValidationError, match="P99"):
        validate_dataset(broken)


def test_validation_detects_dangling_dependency(dataset: AtlasBankDataset) -> None:
    bad = Dependency(source_id=FOCAL_SYSTEM_ID, source_type="system", relation="DEPENDS_ON",
                     target_id="V99", target_type="vendor")
    broken = dataset.model_copy(update={"dependencies": dataset.dependencies + [bad]})
    with pytest.raises(DatasetValidationError, match="V99"):
        validate_dataset(broken)


def test_validation_detects_future_dated_incident(dataset: AtlasBankDataset) -> None:
    late = Incident(**{**dataset.incidents[0].model_dump(), "incident_id": "INC9999",
                       "date": DATA_END + timedelta(days=1)})
    broken = dataset.model_copy(update={"incidents": dataset.incidents + [late]})
    with pytest.raises(DatasetValidationError, match="INC9999"):
        validate_dataset(broken, max_date=DATA_END)


def test_row_schemas_reject_invalid_values(dataset: AtlasBankDataset) -> None:
    base = dataset.incidents[0].model_dump()
    with pytest.raises(ValidationError):
        Incident(**{**base, "financial_loss": -1.0})
    with pytest.raises(ValidationError):
        Incident(**{**base, "category": "meteor_strike"})
    with pytest.raises(ValidationError):
        Incident(**{**base, "severity": "catastrophic"})
    with pytest.raises(ValidationError):
        Incident(**{**base, "date": "2023-02-30"})


def test_dependency_schema_rejects_invalid_relations() -> None:
    with pytest.raises(ValidationError):
        Dependency(source_id="P01", source_type="process", relation="DEPENDS_ON",
                   target_id="V01", target_type="vendor")
    with pytest.raises(ValidationError):
        Dependency(source_id="S1", source_type="system", relation="SUPPORTS",
                   target_id="V01", target_type="vendor")
    with pytest.raises(ValidationError):
        Dependency(source_id="S1", source_type="system", relation="DEPENDS_ON",
                   target_id="S1", target_type="system")


# ----------------------------------------------------------------- focal system story


def _vendors_of(dataset: AtlasBankDataset, system_id: str) -> set[str]:
    return {d.target_id for d in dataset.dependencies
            if d.source_id == system_id and d.relation == "DEPENDS_ON" and d.target_type == "vendor"}


def test_payment_engines_share_a_vendor(dataset: AtlasBankDataset) -> None:
    shared = _vendors_of(dataset, "PAYMENT_ENGINE_01") & _vendors_of(dataset, "PAYMENT_ENGINE_02")
    assert shared == {"V04"}


def test_focal_system_has_process_and_system_dependencies(dataset: AtlasBankDataset) -> None:
    deps = [d for d in dataset.dependencies if d.source_id == FOCAL_SYSTEM_ID]
    assert any(d.relation == "SUPPORTS" and d.target_id == "P01" for d in deps)
    assert any(d.relation == "DEPENDS_ON" and d.target_type == "system" for d in deps)


def test_focal_system_has_recent_incidents(dataset: AtlasBankDataset) -> None:
    cutoff = DATA_END - timedelta(days=365)
    recent = [i for i in dataset.incidents if i.system_id == FOCAL_SYSTEM_ID and i.date > cutoff]
    assert len(recent) >= 3
    deployment = [i for i in recent if "deployment" in i.description.lower()]
    assert len(deployment) >= 2


def test_focal_system_has_overdue_control_but_it_is_not_unique(dataset: AtlasBankDataset) -> None:
    overdue = [c for c in dataset.controls if c.review_status == "overdue"]
    assert any(c.system_id == FOCAL_SYSTEM_ID for c in overdue)
    assert any(c.system_id != FOCAL_SYSTEM_ID for c in overdue)


def test_focal_kris_worsen_but_are_not_the_only_drift(dataset: AtlasBankDataset) -> None:
    def mean(system: str, kri: str, first: bool) -> float:
        values = [k.value for k in dataset.kri_observations if k.system_id == system and k.kri_name == kri]
        chunk = values[:12] if first else values[-12:]
        return sum(chunk) / len(chunk)

    for kri in ("failed_deployment_rate", "system_downtime_minutes", "control_exception_count"):
        assert mean(FOCAL_SYSTEM_ID, kri, first=False) > mean(FOCAL_SYSTEM_ID, kri, first=True)
    assert mean("CORE_LEDGER_01", "failed_deployment_rate", first=False) > mean(
        "CORE_LEDGER_01", "failed_deployment_rate", first=True
    )


def test_shared_vendor_event_hits_both_payment_engines(dataset: AtlasBankDataset) -> None:
    by_date: dict[date, set[str]] = {}
    for i in dataset.incidents:
        if i.category == "third_party_failure":
            by_date.setdefault(i.date, set()).add(i.system_id)
    assert any({"PAYMENT_ENGINE_01", "PAYMENT_ENGINE_02"} <= systems for systems in by_date.values())
