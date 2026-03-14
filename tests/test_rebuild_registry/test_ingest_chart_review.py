"""
tests/test_rebuild_registry/test_ingest_chart_review.py

PURPOSE:
    Tests for ingest_chart_review() — reads chart_review/human/ and
    chart_review/llm/ subtrees and inserts rows into the chart_review table.

    The chart_review/ group has a unique two-level structure:
        chart_review/
        ├── human/note_0001/   ← human reviewer extracted data from note_0001
        └── llm/note_0001/     ← LLM extracted data from the same note

    So a single note can have BOTH a human and an LLM extraction.
"""

import h5py

from rebuild_registry.ingest.patients import ingest_patient
from rebuild_registry.ingest.chart_review import ingest_chart_review


def _setup_patient(db_conn, h5, source="archive/p.h5"):
    """Insert a patient row first (foreign key requirement)."""
    cur = db_conn.cursor()
    pid = ingest_patient(cur, h5, source)
    db_conn.commit()
    return cur, pid


class TestIngestChartReview:

    def test_both_sources_ingested(self, db_conn, tmp_h5):
        """Our fixture has one human + one LLM review → 2 rows total."""
        path = tmp_h5(chart_review=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_chart_review(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM chart_review").fetchone()[0]
        assert count == 2

    def test_human_review_fields(self, db_conn, tmp_h5):
        """Human reviews should have reviewer filled and model as NULL."""
        path = tmp_h5(chart_review=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_chart_review(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT review_source, reviewer, model, review_date, "
            "tumor_size_cm, location, note_name "
            "FROM chart_review WHERE review_source='human'"
        ).fetchone()
        src, reviewer, model, rdate, tumor, loc, note = row

        assert src == "human"
        assert reviewer == "Dr. Chen"     # Human reviewer name
        assert model is None              # No model for human reviews
        assert rdate == "2026-04-15"
        assert abs(tumor - 3.2) < 0.01
        assert loc == "right upper lobe"
        assert note == "note_0001"        # Which note was reviewed

    def test_llm_review_fields(self, db_conn, tmp_h5):
        """LLM reviews should have model filled and reviewer as NULL."""
        path = tmp_h5(chart_review=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_chart_review(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT review_source, reviewer, model, review_date, tumor_size_cm "
            "FROM chart_review WHERE review_source='llm'"
        ).fetchone()
        src, reviewer, model, rdate, tumor = row

        assert src == "llm"
        assert reviewer is None           # No human reviewer
        assert model == "claude-opus-4-6" # LLM model name
        assert rdate == "2026-04-10"      # Falls back to run_date
        assert abs(tumor - 3.1) < 0.01

    def test_group_paths(self, db_conn, tmp_h5):
        """Stored paths should include the human/llm subtree level."""
        path = tmp_h5(chart_review=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_chart_review(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        paths = {r[0] for r in cur.execute("SELECT group_path FROM chart_review").fetchall()}
        assert "/chart_review/human/note_0001" in paths
        assert "/chart_review/llm/note_0001" in paths

    def test_no_chart_review_group(self, db_conn, tmp_h5):
        """If chart_review/ doesn't exist, zero rows and no errors."""
        path = tmp_h5(chart_review=False)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_chart_review(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM chart_review").fetchone()[0]
        assert count == 0

    def test_only_human_subtree(self, db_conn, tmp_path):
        """If only human/ exists (no llm/), only human reviews are ingested."""
        # Build a custom .h5 with only the human subtree
        path = tmp_path / "partial.h5"
        with h5py.File(str(path), "w") as h5:
            h5.attrs["patient_id"] = "P050"
            h5.attrs["created_date"] = "2026-01-01"
            cr = h5.create_group("chart_review")
            human = cr.create_group("human")
            n = human.create_group("note_0001")
            n.attrs["reviewer"] = "Dr. A"
            n.attrs["review_date"] = "2026-05-01"

        # Manually insert the patient row
        cur = db_conn.cursor()
        cur.execute("INSERT INTO patients (patient_id, source_file) VALUES ('P050', 'x.h5')")
        db_conn.commit()

        with h5py.File(str(path), "r") as h5:
            ingest_chart_review(cur, h5, "P050", "archive/partial.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM chart_review").fetchone()[0]
        assert count == 1
        src = cur.execute("SELECT review_source FROM chart_review").fetchone()[0]
        assert src == "human"
