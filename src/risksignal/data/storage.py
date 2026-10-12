"""CSV and SQLite storage for the synthetic Atlas Bank dataset.

CSV files are the human-readable copy. SQLite (``atlas_bank.db``) is the main data
source used by the rest of the application. Only Python's ``sqlite3`` is used.
"""

import csv
import sqlite3
from pathlib import Path
from typing import get_args

import pandas as pd

from risksignal.data.schemas import (
    AtlasBankDataset,
    ControlType,
    Criticality,
    EntityType,
    IncidentCategory,
    KriName,
    Relation,
    ReviewStatus,
    Severity,
    TABLE_MODELS,
    validate_dataset,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"
DB_FILENAME = "atlas_bank.db"


def _in_list(literal_type: object) -> str:
    """Render the allowed values of a Literal as an SQL list, e.g. ('low','high')."""
    return "(" + ",".join(f"'{value}'" for value in get_args(literal_type)) + ")"


SCHEMA_SQL = f"""
CREATE TABLE processes (
    process_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE vendors (
    vendor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE systems (
    system_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    criticality TEXT NOT NULL CHECK (criticality IN {_in_list(Criticality)}),
    primary_process_id TEXT NOT NULL REFERENCES processes (process_id)
);
CREATE TABLE controls (
    control_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    control_type TEXT NOT NULL CHECK (control_type IN {_in_list(ControlType)}),
    system_id TEXT NOT NULL REFERENCES systems (system_id),
    last_review_date TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN {_in_list(ReviewStatus)})
);
CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    system_id TEXT NOT NULL REFERENCES systems (system_id),
    category TEXT NOT NULL CHECK (category IN {_in_list(IncidentCategory)}),
    description TEXT NOT NULL,
    financial_loss REAL NOT NULL CHECK (financial_loss >= 0),
    severity TEXT NOT NULL CHECK (severity IN {_in_list(Severity)})
);
CREATE TABLE kri_observations (
    date TEXT NOT NULL,
    system_id TEXT NOT NULL REFERENCES systems (system_id),
    kri_name TEXT NOT NULL CHECK (kri_name IN {_in_list(KriName)}),
    value REAL NOT NULL CHECK (value >= 0),
    PRIMARY KEY (date, system_id, kri_name)
);
CREATE TABLE dependencies (
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN {_in_list(EntityType)}),
    relation TEXT NOT NULL CHECK (relation IN {_in_list(Relation)}),
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN {_in_list(EntityType)}),
    PRIMARY KEY (source_id, relation, target_id)
);
CREATE INDEX idx_incidents_system_date ON incidents (system_id, date);
CREATE INDEX idx_kri_system ON kri_observations (system_id, kri_name, date);
CREATE INDEX idx_controls_system ON controls (system_id);
"""


def write_csvs(dataset: AtlasBankDataset, directory: Path) -> list[Path]:
    """Write one CSV per table into ``directory`` (created if needed)."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for table, model in TABLE_MODELS.items():
        path = directory / f"{table}.csv"
        columns = list(model.model_fields)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for row in getattr(dataset, table):
                writer.writerow(row.model_dump(mode="json"))
        paths.append(path)
    return paths


def read_csvs(directory: Path) -> AtlasBankDataset:
    """Read and validate the CSV files in ``directory`` into a dataset."""
    tables: dict[str, list[object]] = {}
    for table, model in TABLE_MODELS.items():
        with (directory / f"{table}.csv").open(newline="", encoding="utf-8") as handle:
            tables[table] = [model.model_validate(row) for row in csv.DictReader(handle)]
    dataset = AtlasBankDataset(**tables)
    validate_dataset(dataset)
    return dataset


def init_db(db_path: Path) -> None:
    """Create an empty database with the Atlas Bank schema, replacing any existing tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        for table in reversed(list(TABLE_MODELS)):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def load_csvs_into_db(csv_dir: Path, db_path: Path) -> dict[str, int]:
    """Load the validated CSV files into an initialised database; return row counts."""
    dataset = read_csvs(csv_dir)
    counts: dict[str, int] = {}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for table, model in TABLE_MODELS.items():
            columns = list(model.model_fields)
            placeholders = ",".join("?" for _ in columns)
            sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
            rows = [tuple(row.model_dump(mode="json")[c] for c in columns) for row in getattr(dataset, table)]
            conn.executemany(sql, rows)
            counts[table] = len(rows)
        conn.commit()
    finally:
        conn.close()
    return counts


def save_atlas_bank(dataset: AtlasBankDataset, directory: Path = DEFAULT_DATA_DIR) -> Path:
    """Write CSVs, then build ``atlas_bank.db`` from those CSVs. Return the database path."""
    validate_dataset(dataset)
    write_csvs(dataset, directory)
    db_path = directory / DB_FILENAME
    init_db(db_path)
    load_csvs_into_db(directory, db_path)
    return db_path


def connect(db_path: Path = DEFAULT_DATA_DIR / DB_FILENAME) -> sqlite3.Connection:
    """Open an existing database with foreign keys on and rows accessible by column name."""
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"{db_path} not found. Generate it first: python -m risksignal.data.generator"
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def read_table(table: str, db_path: Path = DEFAULT_DATA_DIR / DB_FILENAME) -> pd.DataFrame:
    """Return a whole table as a DataFrame. ``table`` must be one of the known tables."""
    if table not in TABLE_MODELS:
        raise ValueError(f"unknown table: {table}")
    conn = connect(db_path)
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)
    finally:
        conn.close()
