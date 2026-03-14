"""Ingest patient-level metadata: root attributes + demographics/ group."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import h5py

from ..helpers import attr, attr_list


def ingest_patient(cur: sqlite3.Cursor, h5: h5py.File, source_file: str) -> str:
    """
    Read root-level attributes and the demographics/ group.
    Inserts one row into the ``patients`` table and returns the patient_id.
    """
    patient_id = attr(h5, "patient_id") or Path(source_file).stem

    # Root-level attributes
    tags = attr_list(h5, "tags")
    active_irbs = attr_list(h5, "active_irbs")
    irb_history = attr_list(h5, "irb_history")
    created_date = attr(h5, "created_date")

    # Demographics group
    demo = h5.get("demographics")
    age = attr(demo, "age") if demo else None
    sex = attr(demo, "sex") if demo else None
    diagnosis = attr(demo, "diagnosis") if demo else None
    staging = attr(demo, "staging") if demo else None

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
