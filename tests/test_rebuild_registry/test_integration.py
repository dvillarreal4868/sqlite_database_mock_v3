"""Integration tests — full rebuild_registry pipeline."""

import shutil
import sqlite3

from rebuild_registry import rebuild
from rebuild_registry.schema import table_counts


class TestRebuildEmpty:
    def test_empty_archive_creates_valid_db(self, tmp_path):
        archive = tmp_path / "archive"
        archive.mkdir()
        db_path = tmp_path / "registry" / "registry.db"

        rebuild(archive_dir=archive, db_path=db_path)

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)
        assert all(v == 0 for v in counts.values())
        conn.close()

    def test_idempotent_double_run(self, tmp_path):
        archive = tmp_path / "archive"
        archive.mkdir()
        db_path = tmp_path / "registry" / "registry.db"

        rebuild(archive_dir=archive, db_path=db_path)
        rebuild(archive_dir=archive, db_path=db_path)

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)
        assert all(v == 0 for v in counts.values())
        conn.close()


class TestRebuildPopulated:
    def test_full_patient_file(self, tmp_path, sample_h5_path):
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        shutil.copy(str(sample_h5_path), str(archive / "patient_001.h5"))

        db_path = tmp_path / "registry" / "registry.db"
        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)

        assert counts["patients"] == 1
        assert counts["imaging"] >= 1
        assert counts["data_entries"] >= 2
        assert counts["notes"] >= 1
        assert counts["chart_review"] >= 2
        assert counts["genomics"] >= 1
        conn.close()

    def test_multiple_patient_files(self, tmp_path, tmp_h5):
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)

        p1 = tmp_h5(patient_id="P001", imaging=True, notes=True)
        p2 = tmp_h5(patient_id="P002", data_ts=True, genomics=True)
        shutil.copy(str(p1), str(archive / "patient_001.h5"))
        shutil.copy(str(p2), str(archive / "patient_002.h5"))

        db_path = tmp_path / "registry" / "registry.db"
        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        counts = table_counts(conn)

        assert counts["patients"] == 2
        assert counts["imaging"] >= 1
        assert counts["notes"] >= 1
        assert counts["data_entries"] >= 1
        assert counts["genomics"] >= 1
        conn.close()

    def test_rebuild_reflects_deletions(self, tmp_path, tmp_h5):
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        db_path = tmp_path / "registry" / "registry.db"

        p1 = tmp_h5(patient_id="P001", imaging=True)
        shutil.copy(str(p1), str(archive / "patient_001.h5"))

        rebuild(archive_dir=archive, db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 1
        conn.close()

        (archive / "patient_001.h5").unlink()
        rebuild(archive_dir=archive, db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 0
        conn.close()

    def test_corrupt_file_skipped(self, tmp_path, tmp_h5):
        archive = tmp_path / "archive"
        archive.mkdir(exist_ok=True)
        db_path = tmp_path / "registry" / "registry.db"

        (archive / "patient_bad.h5").write_text("this is not hdf5")

        good = tmp_h5(patient_id="P001")
        shutil.copy(str(good), str(archive / "patient_001.h5"))

        rebuild(archive_dir=archive, db_path=db_path)

        conn = sqlite3.connect(str(db_path))
        assert table_counts(conn)["patients"] == 1
        conn.close()
