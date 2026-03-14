"""
tests/test_rebuild_registry/test_integration.py

PURPOSE:
    Integration tests that exercise the FULL rebuild pipeline end-to-end.

    Unlike the unit tests (which test individual ingest functions in isolation),
    these tests call rebuild() — the same function that runs when you do
    `python -m rebuild_registry`.  They verify:

      - An empty archive produces a valid but empty database.
      - Running rebuild twice (idempotency) doesn't break anything.
      - A fully-populated .h5 file produces rows in every table.
      - Multiple patient files are all ingested.
      - Deleting a file from archive/ and rebuilding removes it from the DB.
      - A corrupt .h5 file is skipped without crashing the whole rebuild.
"""

import shutil
import sqlite3

from rebuild_registry import rebuild
from rebuild_registry.schema import table_counts


class TestRebuildEmpty:
    """Tests with an empty archive/ directory (no .h5 files)."""

    def test_empty_archive_creates_valid_db(self, tmp_path):
        """An empty archive should produce a database with all tables but zero rows."""
        # Set up temporary directories that mimic the real project layout
        archive = tmp_path / "archive"
        archive.mkdir()
        db_path = tmp_path / "registry" / "registry.db"

        # Run the rebuild
        rebuild(archive_dir=archive, db_path=db_path)

        # Verify the database file was created
        assert db_path.exists()

        # Verify all tables exist and are empty
        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)
        assert all(v == 0 for v in counts.values())
        conn.close()

    def test_idempotent_double_run(self, tmp_path):
        """Running rebuild twice on the same empty archive should produce
        the same result — a valid, empty database."""
        archive = tmp_path / "archive"
        archive.mkdir()
        db_path = tmp_path / "registry" / "registry.db"

        rebuild(archive_dir=archive, db_path=db_path)   # First run
        rebuild(archive_dir=archive, db_path=db_path)   # Second run

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)
        assert all(v == 0 for v in counts.values())
        conn.close()


class TestRebuildPopulated:
    """Tests with .h5 files in the archive/ directory."""

    def test_full_patient_file(self, tmp_path, sample_h5_path):
        """A fully-populated .h5 file should produce rows in every table."""
        # Create an archive/ directory and copy the sample file into it
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        shutil.copy(str(sample_h5_path), str(archive / "patient_001.h5"))

        db_path = tmp_path / "registry" / "registry.db"
        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)

        # Every table should have at least one row
        assert counts["patients"] == 1
        assert counts["imaging"] >= 1
        assert counts["data_entries"] >= 2     # glucose (time-series) + pft (single-point)
        assert counts["notes"] >= 1
        assert counts["chart_review"] >= 2     # human + llm
        assert counts["genomics"] >= 1
        conn.close()

    def test_multiple_patient_files(self, tmp_path, tmp_h5):
        """Two different patient .h5 files should produce 2 patient rows."""
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)

        # Create two different patient files with different data
        p1 = tmp_h5(patient_id="P001", imaging=True, notes=True)
        p2 = tmp_h5(patient_id="P002", data_ts=True, genomics=True)
        shutil.copy(str(p1), str(archive / "patient_001.h5"))
        shutil.copy(str(p2), str(archive / "patient_002.h5"))

        db_path = tmp_path / "registry" / "registry.db"
        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)

        assert counts["patients"] == 2       # Two patients
        assert counts["imaging"] >= 1        # From P001
        assert counts["notes"] >= 1          # From P001
        assert counts["data_entries"] >= 1   # From P002
        assert counts["genomics"] >= 1       # From P002
        conn.close()

    def test_rebuild_reflects_deletions(self, tmp_path, tmp_h5):
        """If a file is removed from archive/ and we rebuild, it should
        disappear from the database.  This proves idempotency — the DB
        always mirrors the current state of archive/, nothing more."""
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        db_path = tmp_path / "registry" / "registry.db"

        # First rebuild: one patient file
        p1 = tmp_h5(patient_id="P001", imaging=True)
        shutil.copy(str(p1), str(archive / "patient_001.h5"))

        rebuild(archive_dir=archive, db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 1
        conn.close()

        # Delete the file from archive/
        (archive / "patient_001.h5").unlink()

        # Second rebuild: archive is now empty
        rebuild(archive_dir=archive, db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 0   # Gone from DB too
        conn.close()

    def test_corrupt_file_skipped(self, tmp_path, tmp_h5):
        """A corrupt .h5 file should be logged and skipped — the good file
        should still be ingested successfully."""
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        db_path = tmp_path / "registry" / "registry.db"

        # Write a corrupt file (not valid HDF5)
        (archive / "patient_bad.h5").write_text("this is not hdf5")

        # Write a good file
        good = tmp_h5(patient_id="P001")
        shutil.copy(str(good), str(archive / "patient_001.h5"))

        # Rebuild should NOT crash — it should skip the bad file
        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 1   # Only the good file
        conn.close()
