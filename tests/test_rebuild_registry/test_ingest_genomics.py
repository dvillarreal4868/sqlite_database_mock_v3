"""
tests/test_rebuild_registry/test_ingest_genomics.py

PURPOSE:
    Tests for ingest_genomics() — reads genomics/{assay}_{date}/ groups
    and inserts rows into the genomics table.
"""

import h5py

from rebuild_registry.ingest.patients import ingest_patient
from rebuild_registry.ingest.genomics import ingest_genomics


def _setup_patient(db_conn, h5, source="archive/p.h5"):
    """Insert a patient row first (foreign key requirement)."""
    cur = db_conn.cursor()
    pid = ingest_patient(cur, h5, source)
    db_conn.commit()
    return cur, pid


class TestIngestGenomics:

    def test_wgs_ingested(self, db_conn, tmp_h5):
        """A WGS assay subgroup should produce exactly one row."""
        path = tmp_h5(genomics=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_genomics(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM genomics").fetchone()[0]
        assert count == 1

    def test_genomics_attributes(self, db_conn, tmp_h5):
        """Verify every column value matches what we wrote into the .h5 file."""
        path = tmp_h5(genomics=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_genomics(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT assay, sequencing_platform, coverage, reference_genome, "
            "vcf_path, bam_path, group_path FROM genomics"
        ).fetchone()
        assay, platform, cov, ref, vcf, bam, gpath = row

        assert assay == "wgs"                               # Parsed from "wgs_2026-07-15"
        assert platform == "Illumina NovaSeq"
        assert cov == 30
        assert ref == "GRCh38"
        assert vcf == "/genomics_archive/P001/variants/"    # External path
        assert bam == "/genomics_archive/P001/aligned/"     # External path
        assert gpath == "/genomics/wgs_2026-07-15"          # Full HDF5 path

    def test_no_genomics_group(self, db_conn, tmp_h5):
        """If genomics/ doesn't exist, zero rows and no errors."""
        path = tmp_h5(genomics=False)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_genomics(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM genomics").fetchone()[0]
        assert count == 0
