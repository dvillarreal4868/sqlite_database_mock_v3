"""
rebuild_registry/core.py

PURPOSE:
    This is the orchestrator — the "conductor" of the whole rebuild process.
    It coordinates the following steps in order:

      1. Delete the old registry.db file (if it exists).
      2. Create a brand-new empty database with all 6 tables.
      3. Find every .h5 file in the archive/ directory.
      4. For each .h5 file, open it and call all 6 ingest functions
         (patients, imaging, data, notes, chart_review, genomics).
      5. Commit everything to the database.
      6. Print a summary of how many rows ended up in each table.

    The `rebuild()` function takes explicit paths as arguments — it has
    NO hardcoded paths.  This is important for two reasons:
      - __main__.py can pass in the real project paths.
      - Tests can pass in temporary directories.

IDEMPOTENCY:
    Because we delete and recreate the database every time, running this
    script twice always gives the same result.  The database always
    reflects exactly what's currently in archive/, nothing more.
"""

from __future__ import annotations

import logging
from pathlib import Path

import h5py  # The library that reads HDF5 (.h5) files

# Relative imports: the dot means "from this same package"
from .schema import create_db, table_counts, ALL_TABLES
from .ingest import (
    ingest_patient,
    ingest_imaging,
    ingest_data,
    ingest_notes,
    ingest_chart_review,
    ingest_genomics,
)

# Create a logger for this module.  Messages will appear as:
#   14:30:01  INFO      Processing archive/patient_001.h5
log = logging.getLogger(__name__)


def rebuild(archive_dir: Path, db_path: Path) -> None:
    """
    Delete the old database, create a fresh one, and populate it by
    reading every .h5 file in `archive_dir`.

    Parameters
    ----------
    archive_dir : Path
        The directory containing patient .h5 files.
        Example: /your_project/archive/

    db_path : Path
        Where to create the SQLite database file.
        Example: /your_project/registry/registry.db
    """

    # --- Convert to Path objects if strings were passed in ---
    archive_dir = Path(archive_dir)
    db_path = Path(db_path)

    # --- Make sure the archive directory exists ---
    # `parents=True`  = create parent directories too if needed
    # `exist_ok=True` = don't error if it already exists
    archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # STEP 1 & 2: Delete old DB (if any) and create a fresh one.
    # create_db() handles both steps — see schema.py for details.
    # It returns an open SQLite connection we can use to insert data.
    # ------------------------------------------------------------------
    conn = create_db(db_path)

    # A "cursor" is like a pointer into the database.  We use it to
    # execute SQL statements (INSERT, SELECT, etc.).
    cur = conn.cursor()

    log.info("Created fresh database with %d tables at %s", len(ALL_TABLES), db_path)

    # ------------------------------------------------------------------
    # STEP 3: Find all .h5 files in the archive directory.
    # .rglob("*.h5") searches recursively — it finds .h5 files in
    # subdirectories too, not just the top level.
    # sorted() ensures we process them in alphabetical order.
    # ------------------------------------------------------------------
    h5_files = sorted(archive_dir.rglob("*.h5"))
    log.info("Found %d .h5 file(s) in %s", len(h5_files), archive_dir)

    # ------------------------------------------------------------------
    # STEP 4: Process each .h5 file.
    # ------------------------------------------------------------------

    # We want to store a relative path (like "archive/patient_001.h5")
    # in the database, not the full absolute path.  To do that, we
    # compute paths relative to the archive's parent directory.
    base_dir = archive_dir.parent  # e.g. /your_project/

    for h5_path in h5_files:

        # Convert absolute path to relative path for storage in the DB.
        # Example:
        #   h5_path  = /your_project/archive/patient_001.h5
        #   base_dir = /your_project/
        #   rel      = "archive/patient_001.h5"
        rel = str(h5_path.relative_to(base_dir))
        log.info("Processing %s", rel)

        try:
            # Open the .h5 file in READ-ONLY mode ("r").
            # The `with` statement ensures the file is properly closed
            # even if an error occurs inside the block.
            with h5py.File(str(h5_path), "r") as h5:

                # --- Call each ingest function in order ---
                #
                # ingest_patient runs FIRST because it creates the patient
                # row, and all other tables have a foreign key pointing to
                # that patient_id.  It returns the patient_id string so
                # the other functions can reference it.
                patient_id = ingest_patient(cur, h5, rel)

                # Each of these checks for its corresponding group
                # (e.g., "imaging/", "data/", "Notes/") inside the .h5
                # file.  If the group doesn't exist, it silently does
                # nothing — not every patient has every data type.
                ingest_imaging(cur, h5, patient_id, rel)
                ingest_data(cur, h5, patient_id, rel)
                ingest_notes(cur, h5, patient_id, rel)
                ingest_chart_review(cur, h5, patient_id, rel)
                ingest_genomics(cur, h5, patient_id, rel)

        except Exception:
            # If ANYTHING goes wrong with this file (corrupt file, missing
            # attributes, permission error, etc.), we log the full error
            # traceback and move on to the next file.  One bad file should
            # not crash the entire rebuild.
            log.exception("Failed to process %s — skipping", rel)

    # ------------------------------------------------------------------
    # STEP 5: Commit all the inserted rows to the database.
    # Until we call commit(), the data is in a temporary state.
    # If the script crashed before this line, the DB would be empty.
    # ------------------------------------------------------------------
    conn.commit()

    # ------------------------------------------------------------------
    # STEP 6: Print a summary.
    # table_counts() runs a SELECT COUNT(*) on each table and returns
    # a dictionary like {"patients": 5, "imaging": 12, ...}
    # ------------------------------------------------------------------
    for name, count in table_counts(conn).items():
        log.info("  %-14s %d rows", name, count)

    # Close the database connection (releases the file lock).
    conn.close()
    log.info("Registry rebuild complete.")
