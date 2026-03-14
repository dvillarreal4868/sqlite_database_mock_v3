"""Tests for rebuild_registry.schema — table creation and helper functions."""

from rebuild_registry.schema import create_db, table_counts, ALL_TABLES


class TestCreateDb:
    def test_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = create_db(db_path)
        cur = conn.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for t in ALL_TABLES:
            assert t in tables, f"Missing table: {t}"
        conn.close()

    def test_idempotent_recreates(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn1 = create_db(db_path)
        conn1.execute("INSERT INTO patients (patient_id, source_file) VALUES ('X', 'x.h5')")
        conn1.commit()
        conn1.close()

        conn2 = create_db(db_path)
        count = conn2.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        assert count == 0
        conn2.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = create_db(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()


class TestTableCounts:
    def test_all_zero_on_fresh_db(self, db_conn):
        counts = table_counts(db_conn)
        assert set(counts.keys()) == set(ALL_TABLES)
        assert all(v == 0 for v in counts.values())
