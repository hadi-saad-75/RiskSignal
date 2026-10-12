"""Tests for CSV and SQLite storage of the synthetic Atlas Bank dataset."""

import sqlite3
from pathlib import Path

import pytest

from risksignal.data.generator import DEFAULT_SEED, FOCAL_SYSTEM_ID, generate_atlas_bank
from risksignal.data.schemas import TABLE_MODELS, AtlasBankDataset
from risksignal.data.storage import (
    DB_FILENAME,
    connect,
    init_db,
    load_csvs_into_db,
    read_csvs,
    read_table,
    save_atlas_bank,
    write_csvs,
)


@pytest.fixture(scope="module")
def dataset() -> AtlasBankDataset:
    return generate_atlas_bank(DEFAULT_SEED)


@pytest.fixture(scope="module")
def db_path(dataset: AtlasBankDataset, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return save_atlas_bank(dataset, tmp_path_factory.mktemp("atlas"))


def test_csv_files_are_written_for_every_table(dataset: AtlasBankDataset, tmp_path: Path) -> None:
    paths = write_csvs(dataset, tmp_path)
    assert {p.name for p in paths} == {f"{t}.csv" for t in TABLE_MODELS}
    header = (tmp_path / "incidents.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "incident_id,date,system_id,category,description,financial_loss,severity"


def test_csv_round_trip_preserves_dataset(dataset: AtlasBankDataset, tmp_path: Path) -> None:
    write_csvs(dataset, tmp_path)
    assert read_csvs(tmp_path) == dataset


def test_same_seed_writes_identical_csv_files(dataset: AtlasBankDataset, tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    write_csvs(dataset, first)
    write_csvs(generate_atlas_bank(DEFAULT_SEED), second)
    for table in TABLE_MODELS:
        assert (first / f"{table}.csv").read_bytes() == (second / f"{table}.csv").read_bytes()


def test_save_creates_database_next_to_csvs(db_path: Path) -> None:
    assert db_path.name == DB_FILENAME == "atlas_bank.db"
    assert db_path.exists()
    assert (db_path.parent / "systems.csv").exists()


def test_database_row_counts_match_dataset(dataset: AtlasBankDataset, db_path: Path) -> None:
    conn = connect(db_path)
    try:
        for table in TABLE_MODELS:
            (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            assert count == len(getattr(dataset, table)), table
    finally:
        conn.close()


def test_database_content_matches_dataset(dataset: AtlasBankDataset, db_path: Path) -> None:
    incidents = read_table("incidents", db_path)
    expected = [i for i in dataset.incidents if i.system_id == FOCAL_SYSTEM_ID]
    actual = incidents[incidents.system_id == FOCAL_SYSTEM_ID].sort_values("incident_id")
    assert list(actual.incident_id) == [i.incident_id for i in expected]
    assert list(actual.financial_loss) == [i.financial_loss for i in expected]
    assert (read_table("systems", db_path).system_id == FOCAL_SYSTEM_ID).any()


def test_shared_vendor_is_queryable_in_sqlite(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT a.target_id FROM dependencies a JOIN dependencies b
              ON a.target_id = b.target_id AND a.target_type = 'vendor'
            WHERE a.source_id = 'PAYMENT_ENGINE_01' AND b.source_id = 'PAYMENT_ENGINE_02'
            """
        ).fetchall()
    finally:
        conn.close()
    assert [r["target_id"] for r in rows] == ["V04"]


def test_database_enforces_foreign_keys(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO incidents VALUES ('INC9999','2024-01-01','NO_SUCH_SYSTEM',"
                "'human_error','x',10.0,'low')"
            )
    finally:
        conn.close()


def test_database_rejects_negative_loss_and_bad_category(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO incidents VALUES ('INC9998','2024-01-01','{FOCAL_SYSTEM_ID}',"
                "'human_error','x',-5.0,'low')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO incidents VALUES ('INC9997','2024-01-01','{FOCAL_SYSTEM_ID}',"
                "'meteor_strike','x',5.0,'low')"
            )
    finally:
        conn.close()


def test_init_db_resets_existing_data(dataset: AtlasBankDataset, tmp_path: Path) -> None:
    write_csvs(dataset, tmp_path)
    db = tmp_path / DB_FILENAME
    init_db(db)
    load_csvs_into_db(tmp_path, db)
    init_db(db)
    assert len(read_table("systems", db)) == 0
    counts = load_csvs_into_db(tmp_path, db)
    assert counts["systems"] == 20


def test_connect_missing_database_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        connect(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_read_table_rejects_unknown_table(db_path: Path) -> None:
    with pytest.raises(ValueError):
        read_table("incidents; DROP TABLE systems", db_path)
