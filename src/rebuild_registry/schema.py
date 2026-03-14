"""
rebuild_registry/schema.py

PURPOSE:
    Defines the structure (schema) of the SQLite database and provides
    helper functions to create/destroy the database.

    Think of this file as the "blueprint" for the database.  It answers:
      - What tables exist?
      - What columns does each table have?
      - What data types do the columns use?
      - Which columns link to other tables (foreign keys)?

TABLES (6 total):
    patients      — One row per patient.  The "anchor" table.
    imaging       — One row per imaging session (CT scan, MRI, etc.).
    data_entries  — One row per structured data item (lab results, glucose, PFTs).
    notes         — One row per clinical note (radiology report, pathology note).
    chart_review  — One row per chart review extraction (human or LLM).
    genomics      — One row per genomics assay (WGS, etc.).

    Every table except `patients` has a `patient_id` column that points back
    to the `patients` table.  This is called a "foreign key" — it ensures
    you can't insert an imaging row for a patient that doesn't exist.

COLUMN TYPE CHEAT SHEET (SQLite):
    TEXT     — a string, like "P001" or "CT" or "2026-03-10"
    INTEGER  — a whole number, like 64 or 300
    REAL     — a decimal number, like 2.1 or 0.5
    The "PRIMARY KEY" column uniquely identifies each row.
    "AUTOINCREMENT" means SQLite assigns the next number automatically.
    "NOT NULL" means the column cannot be left empty.
    "REFERENCES patients(patient_id)" is a foreign key constraint.
"""

from __future__ import annotations

import sqlite3          # Python's built-in SQLite database library
from pathlib import Path


# ---------------------------------------------------------------------------
# SQL Schema Definition
# ---------------------------------------------------------------------------
# This is a big string containing SQL commands that create all 6 tables.
# When we run this against a fresh database, it sets up the entire structure.
#
# Note: columns without NOT NULL can be left empty (NULL).  This is
# intentional — not every patient has every field populated.
# ---------------------------------------------------------------------------

SCHEMA_SQL = """

-- =====================================================================
-- PATIENTS TABLE
-- One row per patient.  This is the "parent" table that all others
-- reference via foreign keys.
-- =====================================================================
CREATE TABLE patients (
    patient_id    TEXT PRIMARY KEY,   -- e.g. "P001" — unique per patient
    source_file   TEXT NOT NULL,      -- which .h5 file this came from
    tags          TEXT,               -- JSON list like '["lung_ca", "smoker"]'
    active_irbs   TEXT,               -- JSON list of active IRB protocol IDs
    irb_history   TEXT,               -- JSON list of past IRB protocol IDs
    created_date  TEXT,               -- ISO date the .h5 file was created
    age           INTEGER,            -- patient age from demographics/
    sex           TEXT,               -- "M" or "F" from demographics/
    diagnosis     TEXT,               -- primary diagnosis from demographics/
    staging       TEXT                -- disease staging from demographics/
);

-- =====================================================================
-- IMAGING TABLE
-- One row per imaging session.  A patient can have many scans.
-- Maps to the HDF5 path: imaging/{modality}_{date}/
-- =====================================================================
CREATE TABLE imaging (
    imaging_id       INTEGER PRIMARY KEY AUTOINCREMENT,  -- auto-assigned row ID
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),  -- links to patients
    source_file      TEXT NOT NULL,      -- which .h5 file
    group_path       TEXT NOT NULL,      -- HDF5 path, e.g. "/imaging/ct_2026-03-10"
    modality         TEXT,               -- "CT", "MRI", etc.
    scan_date        TEXT,               -- ISO date of the scan
    num_slices       INTEGER,            -- number of slices in the volume
    voxel_spacing_mm TEXT,               -- JSON list like '[0.5, 0.5, 1.0]'
    body_region      TEXT,               -- "chest", "brain", etc.
    source_irb       TEXT,               -- IRB protocol that provided this data
    volume_shape     TEXT                -- shape string like "(300, 512, 512)"
);

-- =====================================================================
-- DATA_ENTRIES TABLE
-- One row per structured data item.  Covers both:
--   - Time-series data (glucose readings, etc.) where is_timeseries=1
--   - Single-point measurements (PFTs, etc.) where is_timeseries=0
-- Maps to the HDF5 path: data/{data_type}/
-- =====================================================================
CREATE TABLE data_entries (
    data_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    source_file      TEXT NOT NULL,
    group_path       TEXT NOT NULL,      -- e.g. "/data/glucose" or "/data/pft"
    data_type        TEXT,               -- e.g. "pft", "glucose"
    is_timeseries    INTEGER,            -- 1 = time-series, 0 = single-point
    session_date     TEXT,               -- when the data was collected
    sampling_rate_hz REAL,               -- Hz (only for time-series)
    device           TEXT,               -- recording device (only for time-series)
    num_samples      INTEGER,            -- number of data points (only for time-series)
    attributes_json  TEXT                -- JSON dict of all attrs (only for single-point)
);

-- =====================================================================
-- NOTES TABLE
-- One row per clinical note.
-- Maps to the HDF5 path: Notes/note_{NNNN}/
-- =====================================================================
CREATE TABLE notes (
    note_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    TEXT NOT NULL REFERENCES patients(patient_id),
    source_file   TEXT NOT NULL,
    group_path    TEXT NOT NULL,      -- e.g. "/Notes/note_0001"
    note_name     TEXT,               -- e.g. "note_0001"
    author        TEXT,               -- who wrote the note
    date          TEXT,               -- ISO date
    category      TEXT,               -- "radiology", "pathology", "general", etc.
    reviewed      INTEGER,            -- 1 = reviewed, 0 = not reviewed
    char_length   INTEGER             -- number of characters in the note text
);

-- =====================================================================
-- CHART_REVIEW TABLE
-- One row per chart review extraction.  Has two "sources":
--   - "human" = a human reviewer extracted data from a note
--   - "llm"   = an LLM extracted data from a note
-- Maps to: chart_review/human/note_{NNNN}/ or chart_review/llm/note_{NNNN}/
-- =====================================================================
CREATE TABLE chart_review (
    review_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     TEXT NOT NULL REFERENCES patients(patient_id),
    source_file    TEXT NOT NULL,
    group_path     TEXT NOT NULL,     -- e.g. "/chart_review/human/note_0001"
    note_name      TEXT,              -- which note was reviewed (e.g. "note_0001")
    review_source  TEXT,              -- "human" or "llm"
    reviewer       TEXT,              -- human reviewer name (NULL for LLM)
    model          TEXT,              -- LLM model name (NULL for human)
    review_date    TEXT,              -- ISO date of the review
    tumor_size_cm  REAL,              -- extracted tumor size
    location       TEXT               -- extracted anatomical location
);

-- =====================================================================
-- GENOMICS TABLE
-- One row per genomics assay.  Contains metadata and external file paths
-- only — the actual genomic data is too large to store in the .h5 file.
-- Maps to: genomics/{assay}_{date}/
-- =====================================================================
CREATE TABLE genomics (
    genomics_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           TEXT NOT NULL REFERENCES patients(patient_id),
    source_file          TEXT NOT NULL,
    group_path           TEXT NOT NULL,  -- e.g. "/genomics/wgs_2026-07-15"
    assay                TEXT,           -- e.g. "wgs" (whole genome sequencing)
    sequencing_platform  TEXT,           -- e.g. "Illumina NovaSeq"
    coverage             INTEGER,        -- sequencing depth, e.g. 30
    reference_genome     TEXT,           -- e.g. "GRCh38"
    vcf_path             TEXT,           -- path to variant call files on disk
    bam_path             TEXT            -- path to aligned reads on disk
);
"""

# A tuple listing every table name.  Used by table_counts() and by
# the logging in core.py to iterate over all tables.
ALL_TABLES = (
    "patients",
    "imaging",
    "data_entries",
    "notes",
    "chart_review",
    "genomics",
)


# ---------------------------------------------------------------------------
# Database Lifecycle Functions
# ---------------------------------------------------------------------------

def create_db(db_path: str | Path) -> sqlite3.Connection:
    """
    Create a fresh, empty database at the given path.

    What this does step by step:
      1. Ensures the parent directory exists (creates it if not).
      2. Deletes the old database file if one exists.
      3. Opens a new SQLite connection (this creates the file).
      4. Enables WAL mode (faster concurrent reads).
      5. Enables foreign key enforcement.
      6. Runs all the CREATE TABLE statements from SCHEMA_SQL.
      7. Returns the open connection so the caller can insert data.

    Parameters
    ----------
    db_path : str or Path
        Where to create the database file.
        Example: "/your_project/registry/registry.db"

    Returns
    -------
    sqlite3.Connection
        An open database connection ready for use.
    """
    db_path = Path(db_path)

    # Make sure the directory exists.
    # Example: if db_path is /project/registry/registry.db,
    # this ensures /project/registry/ exists.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Delete the old database if it exists.
    # This is what makes the script idempotent — we always start fresh.
    if db_path.exists():
        db_path.unlink()  # unlink = delete

    # Open a connection.  sqlite3.connect() creates the file if it doesn't exist.
    conn = sqlite3.connect(str(db_path))

    # WAL (Write-Ahead Logging) mode allows readers and writers to operate
    # at the same time.  It's generally faster for our use case.
    conn.execute("PRAGMA journal_mode=WAL;")

    # By default, SQLite does NOT enforce foreign keys.  This turns it on
    # so that, for example, you can't insert an imaging row with a
    # patient_id that doesn't exist in the patients table.
    conn.execute("PRAGMA foreign_keys=ON;")

    # Run all the CREATE TABLE statements defined above.
    # executescript() can run multiple SQL statements separated by semicolons.
    conn.cursor().executescript(SCHEMA_SQL)

    return conn


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Count the number of rows in each table.

    Returns a dictionary like:
        {"patients": 5, "imaging": 12, "data_entries": 8, ...}

    This is used at the end of a rebuild to print a summary.
    """
    cur = conn.cursor()
    return {
        table_name: cur.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        for table_name in ALL_TABLES
    }
