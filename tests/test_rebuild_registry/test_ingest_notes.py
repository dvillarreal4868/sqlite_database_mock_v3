"""Tests for rebuild_registry.ingest.notes."""

import h5py

from rebuild_registry.ingest.patients import ingest_patient
from rebuild_registry.ingest.notes import ingest_notes


def _setup_patient(db_conn, h5, source="archive/p.h5"):
    cur = db_conn.cursor()
    pid = ingest_patient(cur, h5, source)
    db_conn.commit()
    return cur, pid


class TestIngestNotes:
    def test_two_notes_ingested(self, db_conn, tmp_h5):
        path = tmp_h5(notes=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_notes(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert count == 2

    def test_note_attributes(self, db_conn, tmp_h5):
        path = tmp_h5(notes=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_notes(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT note_name, author, date, category, reviewed, char_length "
            "FROM notes WHERE note_name='note_0001'"
        ).fetchone()
        note_name, author, date, category, reviewed, char_length = row

        assert note_name == "note_0001"
        assert author == "Dr. Smith_1"
        assert date == "2026-03-11"
        assert category == "radiology"
        assert reviewed == 1
        assert char_length is not None and char_length > 0

    def test_reviewed_stored_as_int(self, db_conn, tmp_h5):
        path = tmp_h5(notes=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_notes(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        vals = cur.execute("SELECT reviewed FROM notes").fetchall()
        for (v,) in vals:
            assert v in (0, 1)

    def test_no_notes_group(self, db_conn, tmp_h5):
        path = tmp_h5(notes=False)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_notes(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert count == 0

    def test_group_path_format(self, db_conn, tmp_h5):
        path = tmp_h5(notes=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_notes(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        paths = [r[0] for r in cur.execute("SELECT group_path FROM notes").fetchall()]
        for p in paths:
            assert p.startswith("/Notes/note_")
