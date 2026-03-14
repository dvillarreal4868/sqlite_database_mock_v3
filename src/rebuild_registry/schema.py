"""
rebuild_registry.schema
~~~~~~~~~~~~~~~~~~~~~~~
SQL table definitions and database creation / teardown helpers.
Aligned with file_spec.md v0.1.0-draft.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE patients (
    patient_id    TEXT PRIMARY KEY,
    source_file   TEXT NOT NULL,
    tags          TEXT,            -- JSON list
    active_irbs   TEXT,            -- JSON list
    irb_history   TEXT,            -- JSON list
    created_date  TEXT,
    age           INTEGER,
    sex           TEXT,
    diagnosis     TEXT,
    staging       TEXT
);

CREATE TABLE imaging (
    imaging_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    source_file      TEXT NOT NULL,
    group_path       TEXT NOT NULL,
    modality         TEXT,
    scan_date        TEXT,
    num_slices       INTEGER,
    voxel_spacing_mm TEXT,         -- JSON list of floats
    body_region      TEXT,
    source_irb       TEXT,
    volume_shape     TEXT          -- e.g. "(300, 512, 512)"
);

CREATE TABLE data_entries (
    data_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    source_file      TEXT NOT NULL,
    group_path       TEXT NOT NULL,
    data_type        TEXT,         -- e.g. "pft", "glucose"
    is_timeseries    INTEGER,      -- 0 or 1
    session_date     TEXT,
    sampling_rate_hz REAL,
    device           TEXT,
    num_samples      INTEGER,
    attributes_json  TEXT          -- JSON dict for single-point values
);

CREATE TABLE notes (
    note_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    TEXT NOT NULL REFERENCES patients(patient_id),
    source_file   TEXT NOT NULL,
    group_path    TEXT NOT NULL,
    note_name     TEXT,           -- e.g. "note_0001"
    author        TEXT,
    date          TEXT,
    category      TEXT,
    reviewed      INTEGER,        -- 0 or 1
    char_length   INTEGER
);

CREATE TABLE chart_review (
    review_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     TEXT NOT NULL REFERENCES patients(patient_id),
    source_file    TEXT NOT NULL,
    group_path     TEXT NOT NULL,
    note_name      TEXT,          -- matching note in Notes/
    review_source  TEXT,          -- "human" or "llm"
    reviewer       TEXT,
    model          TEXT,
    review_date    TEXT,
    tumor_size_cm  REAL,
    location       TEXT
);

CREATE TABLE genomics (
    genomics_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           TEXT NOT NULL REFERENCES patients(patient_id),
    source_file          TEXT NOT NULL,
    group_path           TEXT NOT NULL,
    assay                TEXT,
    sequencing_platform  TEXT,
    coverage             INTEGER,
    reference_genome     TEXT,
    vcf_path             TEXT,
    bam_path             TEXT
);
"""

ALL_TABLES = (
    "patients",
    "imaging",
    "data_entries",
    "notes",
    "chart_review",
    "genomics",
)


def create_db(db_path: str | Path) -> sqlite3.Connection:
    """Create a fresh database at *db_path* and return an open connection."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.cursor().executescript(SCHEMA_SQL)
    return conn


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return {table_name: row_count} for every registry table."""
    cur = conn.cursor()
    return {
        t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ALL_TABLES
    }
