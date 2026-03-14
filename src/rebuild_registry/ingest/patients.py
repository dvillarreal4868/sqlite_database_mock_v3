"""
rebuild_registry/ingest/patients.py

PURPOSE:
    Reads patient-level metadata from an HDF5 file and inserts one row
    into the `patients` table.

    This function MUST run before all other ingest functions because
    every other table has a foreign key (patient_id) that references the
    patients table.  If we tried to insert an imaging row first, the
    database would reject it with a foreign key error.

WHERE THE DATA COMES FROM IN THE .h5 FILE:
    Root-level attributes (attached to the file itself):
        patient_id, tags, active_irbs, irb_history, created_date

    demographics/ group attributes:
        age, sex, diagnosis, staging

    Example HDF5 structure:
        patient_001.h5
        ├── [root attrs: patient_id="P001", tags=["lung_ca"], ...]
        └── demographics/
            └── [attrs: age=64, sex="M", diagnosis="NSCLC", staging="Stage III"]
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import h5py

# The double dot (..) means "go up one directory" — i.e., from ingest/ up to
# rebuild_registry/ — and then import from helpers.py
from ..helpers import attr, attr_list


def ingest_patient(cur: sqlite3.Cursor, h5: h5py.File, source_file: str) -> str:
    """
    Read patient data from the HDF5 file and insert into the patients table.

    Parameters
    ----------
    cur : sqlite3.Cursor
        A database cursor for executing SQL statements.
    h5 : h5py.File
        An open HDF5 file (the patient's .h5 file).
    source_file : str
        The relative path to this .h5 file, stored in the DB for reference.
        Example: "archive/patient_001.h5"

    Returns
    -------
    str
        The patient_id (e.g., "P001").  This is returned so that other
        ingest functions can use it when inserting their rows.
    """

    # --- Read patient_id from root attributes ---
    # If the attribute exists, we get something like "P001".
    # If it doesn't exist (malformed file), we fall back to the filename stem.
    # Example fallback: "archive/patient_001.h5" → stem = "patient_001"
    patient_id = attr(h5, "patient_id") or Path(source_file).stem

    # --- Read the other root-level attributes ---
    # These are list-type attributes, so attr_list() returns JSON strings.
    # Example: tags might be '["lung_ca", "smoker"]'
    tags = attr_list(h5, "tags")
    active_irbs = attr_list(h5, "active_irbs")
    irb_history = attr_list(h5, "irb_history")
    created_date = attr(h5, "created_date")

    # --- Read demographics from the demographics/ group ---
    # h5.get("demographics") returns the group if it exists, or None if not.
    # Not all files may have this group, so we check before reading.
    demo = h5.get("demographics")
    age = attr(demo, "age") if demo else None
    sex = attr(demo, "sex") if demo else None
    diagnosis = attr(demo, "diagnosis") if demo else None
    staging = attr(demo, "staging") if demo else None

    # --- Insert into the database ---
    # "INSERT OR IGNORE" means: if a row with this patient_id already exists,
    # skip this insert silently.  This handles the edge case where two .h5
    # files might have the same patient_id (shouldn't happen, but defensive).
    #
    # The (?, ?, ?, ...) syntax uses parameterized queries — the question marks
    # are placeholders that SQLite fills in with the values from the tuple.
    # This is safer than string formatting because it prevents SQL injection.
    cur.execute(
        """INSERT OR IGNORE INTO patients
           (patient_id, source_file, tags, active_irbs, irb_history,
            created_date, age, sex, diagnosis, staging)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            patient_id, source_file, tags, active_irbs, irb_history,
            created_date, age, sex, diagnosis, staging,
        ),
    )

    return patient_id
