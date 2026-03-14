"""
tests/test_rebuild_registry/test_ingest_imaging.py

PURPOSE:
    Tests for ingest_imaging() — reads imaging/{modality}_{date}/ groups
    and inserts rows into the imaging table.
"""

import json

import h5py

from rebuild_registry.ingest.patients import ingest_patient
from rebuild_registry.ingest.imaging import ingest_imaging


def _setup_patient(db_conn, h5, source="archive/p.h5"):
    """
    Helper: insert a patient row first (required because imaging rows
    have a foreign key to patients).  Returns (cursor, patient_id).
    """
    cur = db_conn.cursor()
    pid = ingest_patient(cur, h5, source)
    db_conn.commit()
    return cur, pid


class TestIngestImaging:

    def test_single_ct_session(self, db_conn, tmp_h5):
        """One imaging subgroup should produce exactly one row."""
        path = tmp_h5(imaging=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_imaging(cur, h5, pid, "archive/patient_001.h5")
        db_conn.commit()

        rows = cur.execute("SELECT * FROM imaging").fetchall()
        assert len(rows) == 1

    def test_attributes_match_spec(self, db_conn, tmp_h5):
        """Verify every column value matches what we wrote into the .h5 file."""
        path = tmp_h5(imaging=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_imaging(cur, h5, pid, "archive/patient_001.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT modality, scan_date, num_slices, voxel_spacing_mm, "
            "body_region, source_irb, volume_shape FROM imaging"
        ).fetchone()
        modality, scan_date, num_slices, voxel, body, irb, shape = row

        assert modality == "CT"
        assert scan_date == "2026-03-10"
        assert num_slices == 10
        assert json.loads(voxel) == [0.5, 0.5, 1.0]  # Stored as JSON list
        assert body == "chest"
        assert irb == "IRB-2025-001"
        assert "(10, 512, 512)" in shape

    def test_multiple_sessions(self, db_conn, tmp_path):
        """Two imaging subgroups (CT + MRI) should produce two rows."""
        # Build a custom .h5 file with two imaging sessions
        path = tmp_path / "multi.h5"
        with h5py.File(str(path), "w") as h5:
            h5.attrs["patient_id"] = "P010"
            h5.attrs["created_date"] = "2026-01-01"
            demo = h5.create_group("demographics")
            demo.attrs["age"] = 50
            demo.attrs["sex"] = "F"
            demo.attrs["diagnosis"] = "test"
            demo.attrs["staging"] = "I"

            ig = h5.create_group("imaging")

            ct = ig.create_group("ct_2026-03-10")
            ct.attrs["modality"] = "CT"
            ct.attrs["scan_date"] = "2026-03-10"
            ct.attrs["num_slices"] = 5
            ct.attrs["body_region"] = "chest"
            ct.create_dataset("volume", shape=(5, 512, 512), dtype="int16")

            mri = ig.create_group("mri_2026-05-15")
            mri.attrs["modality"] = "MRI"
            mri.attrs["scan_date"] = "2026-05-15"
            mri.attrs["num_slices"] = 20
            mri.attrs["body_region"] = "brain"
            mri.create_dataset("volume", shape=(20, 256, 256), dtype="int16")

        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_imaging(cur, h5, pid, "archive/multi.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM imaging").fetchone()[0]
        assert count == 2

        modalities = {
            r[0] for r in cur.execute("SELECT modality FROM imaging").fetchall()
        }
        assert modalities == {"CT", "MRI"}

    def test_no_imaging_group(self, db_conn, tmp_h5):
        """If imaging/ doesn't exist, zero rows and no errors."""
        path = tmp_h5(imaging=False)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_imaging(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM imaging").fetchone()[0]
        assert count == 0

    def test_num_slices_from_volume_fallback(self, db_conn, tmp_path):
        """If num_slices attribute is missing, infer it from the volume shape."""
        path = tmp_path / "noslice.h5"
        with h5py.File(str(path), "w") as h5:
            h5.attrs["patient_id"] = "P020"
            h5.attrs["created_date"] = "2026-01-01"
            ig = h5.create_group("imaging")
            sub = ig.create_group("ct_2026-01-01")
            sub.attrs["modality"] = "CT"
            # Intentionally NOT setting num_slices attribute
            sub.create_dataset("volume", shape=(42, 512, 512), dtype="int16")

        # Manually insert patient (bypassing ingest_patient for simplicity)
        cur = db_conn.cursor()
        cur.execute("INSERT INTO patients (patient_id, source_file) VALUES ('P020', 'x.h5')")
        db_conn.commit()

        with h5py.File(str(path), "r") as h5:
            ingest_imaging(cur, h5, "P020", "archive/noslice.h5")
        db_conn.commit()

        num = cur.execute("SELECT num_slices FROM imaging").fetchone()[0]
        assert num == 42  # Should be inferred from volume.shape[0]
