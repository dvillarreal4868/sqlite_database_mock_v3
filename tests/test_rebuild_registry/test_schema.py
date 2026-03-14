"""
tests/test_rebuild_registry/test_schema.py

PURPOSE:
    Tests for the database schema and lifecycle functions in schema.py.

    These tests verify that:
      - create_db() creates all 6 expected tables
      - create_db() is idempotent (running twice wipes and recreates)
      - Foreign key enforcement is turned on
      - table_counts() correctly counts rows

HOW PYTEST WORKS (quick primer):
    - Pytest finds files named test_*.py and functions/methods named test_*.
    - Each test function either passes (no assertion errors) or fails.
    - `assert X == Y` passes if X equals Y, fails otherwise.
    - Fixtures (like `db_conn` and `tmp_path`) are injected by name:
      pytest sees that `test_creates_all_tables(self, tmp_path)` needs
      `tmp_path`, so it provides a temporary directory automatically.
"""

from rebuild_registry.schema import create_db, table_counts, ALL_TABLES


class TestCreateDb:
    """Tests for the create_db() function."""

    def test_creates_all_tables(self, tmp_path):
        """Verify that all 6 tables exist after create_db()."""
        db_path = tmp_path / "test.db"
        conn = create_db(db_path)

        # Query SQLite's internal catalog to get all table names
        cur = conn.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        # Check that every expected table is present
        for t in ALL_TABLES:
            assert t in tables, f"Missing table: {t}"

        conn.close()

    def test_idempotent_recreates(self, tmp_path):
        """Running create_db() twice should wipe the old data."""
        db_path = tmp_path / "test.db"

        # First run: create DB and insert a patient
        conn1 = create_db(db_path)
        conn1.execute("INSERT INTO patients (patient_id, source_file) VALUES ('X', 'x.h5')")
        conn1.commit()
        conn1.close()

        # Second run: should delete the old DB and create a fresh empty one
        conn2 = create_db(db_path)
        count = conn2.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        assert count == 0  # The old row should be gone
        conn2.close()

    def test_foreign_keys_enabled(self, tmp_path):
        """Verify that foreign key constraints are turned on."""
        db_path = tmp_path / "test.db"
        conn = create_db(db_path)
        # PRAGMA foreign_keys returns 1 if enabled, 0 if disabled
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()


class TestTableCounts:
    """Tests for the table_counts() helper function."""

    def test_all_zero_on_fresh_db(self, db_conn):
        """A brand new database should have 0 rows in every table."""
        counts = table_counts(db_conn)
        assert set(counts.keys()) == set(ALL_TABLES)
        assert all(v == 0 for v in counts.values())
