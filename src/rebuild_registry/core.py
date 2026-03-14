"""
rebuild_registry.core
~~~~~~~~~~~~~~~~~~~~~
Orchestrates the full registry rebuild: wipe DB → create schema → walk
archive/ → ingest every .h5 file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import h5py

from .schema import create_db, table_counts, ALL_TABLES
from .ingest import (
    ingest_patient,
    ingest_imaging,
    ingest_data,
    ingest_notes,
    ingest_chart_review,
    ingest_genomics,
)

log = logging.getLogger(__name__)


def rebuild(archive_dir: Path, db_path: Path) -> None:
    """Delete the old DB, create a fresh one, and populate from *archive_dir*.

    This function is idempotent — call it at any time to get a registry that
    exactly reflects the current state of the archive.
    """
    archive_dir = Path(archive_dir)
    db_path = Path(db_path)
    archive_dir.mkdir(parents=True, exist_ok=True)

    conn = create_db(db_path)
    cur = conn.cursor()
    log.info("Created fresh database with %d tables at %s", len(ALL_TABLES), db_path)

    h5_files = sorted(archive_dir.rglob("*.h5"))
    log.info("Found %d .h5 file(s) in %s", len(h5_files), archive_dir)

    base_dir = archive_dir.parent
    for h5_path in h5_files:
        rel = str(h5_path.relative_to(base_dir))
        log.info("Processing %s", rel)
        try:
            with h5py.File(str(h5_path), "r") as h5:
                patient_id = ingest_patient(cur, h5, rel)
                ingest_imaging(cur, h5, patient_id, rel)
                ingest_data(cur, h5, patient_id, rel)
                ingest_notes(cur, h5, patient_id, rel)
                ingest_chart_review(cur, h5, patient_id, rel)
                ingest_genomics(cur, h5, patient_id, rel)
        except Exception:
            log.exception("Failed to process %s — skipping", rel)

    conn.commit()

    for name, count in table_counts(conn).items():
        log.info("  %-14s %d rows", name, count)

    conn.close()
    log.info("Registry rebuild complete.")
