"""Tests for rebuild_registry.ingest.patients."""

import json

import h5py

from rebuild_registry.ingest.patients import ingest_patient


class TestIngestPatient:
    def test_basic_ingest(self, db_conn, tmp_h5):
        path = tmp_h5(patient_id="P042")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            pid = ingest_patient(cur, h5, "archive/patient_042.h5")
        db_conn.commit()

        assert pid == "P042"
        row = cur.execute("SELECT * FROM patients WHERE patient_id='P042'").fetchone()
        assert row is not None

    def test_demographics_populated(self, db_conn, tmp_h5):
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
        assert "lung_ca" in json.loads(tags)
        assert "IRB-2025-001" in json.loads(active_irbs)
        assert "IRB-2024-010" in json.loads(irb_history)
        assert created_date == "2026-01-15"

    def test_fallback_patient_id_from_filename(self, db_conn, tmp_path):
        path = tmp_path / "patient_fallback.h5"
        with h5py.File(str(path), "w") as h5:
            h5.attrs["created_date"] = "2026-01-01"
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            pid = ingest_patient(cur, h5, "archive/patient_fallback.h5")
        assert pid == "patient_fallback"

    def test_no_demographics_group(self, db_conn, tmp_h5):
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
        path = tmp_h5(patient_id="P001")
        cur = db_conn.cursor()
        with h5py.File(str(path), "r") as h5:
            ingest_patient(cur, h5, "file_a.h5")
            ingest_patient(cur, h5, "file_b.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        assert count == 1
