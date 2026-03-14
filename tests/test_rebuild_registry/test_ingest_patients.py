"""
tests/test_rebuild_registry/test_ingest_patients.py

PURPOSE:
    Tests for ingest_patient() — the function that reads root attributes
    and demographics/ from an .h5 file and inserts a row into the patients table.

TEST PATTERN:
    Most tests follow this pattern:
      1. Create a .h5 file using the tmp_h5 fixture.
      2. Open it in read mode.
      3. Call ingest_patient() with a database cursor.
      4. Query the database and assert the results match expectations.
"""

import json

import h5py

from rebuild_registry.ingest.patients import ingest_patient


class TestIngestPatient:

    def test_basic_ingest(self, db_conn, tmp_h5):
        """A simple .h5 file should produce one row with the right patient_id."""
        path = tmp_h5(patient_id="P042")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            pid = ingest_patient(cur, h5, "archive/patient_042.h5")
        db_conn.commit()

        assert pid == "P042"
        row = cur.execute("SELECT * FROM patients WHERE patient_id='P042'").fetchone()
        assert row is not None  # Row should exist

    def test_demographics_populated(self, db_conn, tmp_h5):
        """Age, sex, diagnosis, and staging should be read from demographics/."""
        path = tmp_h5(patient_id="P001")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            ingest_patient(cur, h5, "archive/patient_001.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT age, sex, diagnosis, staging FROM patients WHERE patient_id='P001'"
        ).fetchone()
        age, sex, diagnosis, staging = row
        assert age == 64
        assert sex == "M"
        assert diagnosis == "NSCLC"
        assert staging == "Stage III"

    def test_root_attrs_populated(self, db_conn, tmp_h5):
        """Tags, IRBs, and created_date should be read from root attributes."""
        path = tmp_h5(patient_id="P001")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            ingest_patient(cur, h5, "archive/patient_001.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT tags, active_irbs, irb_history, created_date "
            "FROM patients WHERE patient_id='P001'"
        ).fetchone()
        tags, active_irbs, irb_history, created_date = row

        # Tags and IRBs are stored as JSON strings — parse them to verify
        assert "lung_ca" in json.loads(tags)
        assert "IRB-2025-001" in json.loads(active_irbs)
        assert "IRB-2024-010" in json.loads(irb_history)
        assert created_date == "2026-01-15"

    def test_fallback_patient_id_from_filename(self, db_conn, tmp_path):
        """If patient_id attribute is missing, use the filename as fallback."""
        path = tmp_path / "patient_fallback.h5"
        with h5py.File(str(path), "w") as h5:
            # Intentionally NOT setting patient_id attribute
            h5.attrs["created_date"] = "2026-01-01"
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            pid = ingest_patient(cur, h5, "archive/patient_fallback.h5")
        # Should use "patient_fallback" (the filename stem) as the ID
        assert pid == "patient_fallback"

    def test_no_demographics_group(self, db_conn, tmp_h5):
        """If demographics/ is missing, the patient row should still be created
        but demographic fields (age, sex, etc.) should be NULL."""
        path = tmp_h5(patient_id="P099", demographics=False)
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            ingest_patient(cur, h5, "archive/patient_099.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT age, sex, diagnosis FROM patients WHERE patient_id='P099'"
        ).fetchone()
        assert row == (None, None, None)

    def test_duplicate_patient_ignored(self, db_conn, tmp_h5):
        """INSERT OR IGNORE should silently skip a duplicate patient_id."""
        path = tmp_h5(patient_id="P001")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            ingest_patient(cur, h5, "file_a.h5")  # First insert
            ingest_patient(cur, h5, "file_b.h5")  # Duplicate — should be ignored
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        assert count == 1  # Should still be just 1 row
