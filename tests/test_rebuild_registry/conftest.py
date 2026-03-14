"""
tests/test_rebuild_registry/conftest.py

PURPOSE:
    This file is special to pytest.  Pytest automatically loads any file
    named `conftest.py` and makes its "fixtures" available to all tests
    in the same directory (and subdirectories).

    A "fixture" is a reusable piece of setup code.  Instead of every test
    creating its own database and HDF5 files from scratch, they can just
    request a fixture by name and pytest will provide it.

FIXTURES PROVIDED:
    db_conn         — A fresh in-memory SQLite database with all 6 tables.
                      Tests use this to insert data and check results without
                      touching any file on disk.

    tmp_h5          — A factory function that creates spec-compliant .h5 files.
                      Call it with flags to control which sections to populate:
                          path = tmp_h5(imaging=True, notes=True)
                      This creates a file with patient data, imaging, and notes.

    sample_h5_path  — A pre-built .h5 file with EVERYTHING populated.
                      Convenient for integration tests that want a "full" file.

WHY THIS MATTERS:
    Having good fixtures means each test can focus on ONE thing.  If a test
    is checking that imaging ingest works, it doesn't need 30 lines of
    boilerplate to set up a database and an HDF5 file — it just says
    "give me a db_conn and a tmp_h5 with imaging=True."
"""

from __future__ import annotations

import sqlite3

import h5py
import numpy as np
import pytest

# Import the SQL schema so we can create test databases
from rebuild_registry.schema import SCHEMA_SQL


# =========================================================================
# DATABASE FIXTURE
# =========================================================================

@pytest.fixture
def db_conn():
    """
    Create a fresh in-memory SQLite database with the full registry schema.

    ":memory:" tells SQLite to create the database in RAM, not on disk.
    This makes tests fast and ensures they don't leave files behind.

    The `yield` keyword means:
      1. Everything before `yield` runs BEFORE the test.
      2. The test receives `conn` as its fixture value.
      3. Everything after `yield` runs AFTER the test (cleanup).
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.cursor().executescript(SCHEMA_SQL)
    yield conn          # ← the test runs here, using this connection
    conn.close()        # ← cleanup: close the connection after the test


# =========================================================================
# HDF5 BUILDER HELPERS
# =========================================================================
# These private functions (_write_*) each populate one section of an HDF5
# file according to the file_spec.md.  They're called by the tmp_h5
# fixture below.
# =========================================================================

def _write_root_attrs(h5, patient_id="P001"):
    """Write the required root-level attributes (patient_id, tags, etc.)."""
    h5.attrs["patient_id"] = patient_id
    # np.array(["lung_ca", "smoker"], dtype="S") creates a NumPy array of
    # byte-strings, which is how h5py stores string arrays in HDF5.
    h5.attrs["tags"] = np.array(["lung_ca", "smoker"], dtype="S")
    h5.attrs["active_irbs"] = np.array(["IRB-2025-001"], dtype="S")
    h5.attrs["irb_history"] = np.array(["IRB-2024-010"], dtype="S")
    h5.attrs["created_date"] = "2026-01-15"


def _write_demographics(h5, age=64, sex="M", diagnosis="NSCLC", staging="Stage III"):
    """Create the demographics/ group with patient demographic attributes."""
    grp = h5.create_group("demographics")
    grp.attrs["age"] = age
    grp.attrs["sex"] = sex
    grp.attrs["diagnosis"] = diagnosis
    grp.attrs["staging"] = staging


def _write_imaging(h5, modality="CT", date="2026-03-10", shape=(10, 512, 512)):
    """
    Create an imaging session subgroup with a tiny volume dataset.

    We use shape=(10, 512, 512) instead of a real CT volume (300+ slices)
    to keep tests fast and memory-light.  The registry only reads the shape,
    so the actual data values don't matter.
    """
    # require_group = create if it doesn't exist, return it if it does.
    # This lets multiple calls to _write_imaging() add to the same imaging/ group.
    img_grp = h5.require_group("imaging")
    sub = img_grp.create_group(f"{modality.lower()}_{date}")
    sub.attrs["modality"] = modality
    sub.attrs["scan_date"] = date
    sub.attrs["num_slices"] = shape[0]
    sub.attrs["voxel_spacing_mm"] = np.array([0.5, 0.5, 1.0])
    sub.attrs["body_region"] = "chest"
    sub.attrs["source_irb"] = "IRB-2025-001"
    # Create a dataset with the right shape but don't fill it with real data.
    # The dtype="int16" matches what real CT volumes use.
    sub.create_dataset("volume", shape=shape, dtype="int16")


def _write_data_timeseries(h5, name="glucose", n=100):
    """Create a time-series data entry (e.g., glucose monitoring)."""
    data_grp = h5.require_group("data")
    sub = data_grp.create_group(name)
    sub.attrs["session_date"] = "2026-03-10"
    sub.attrs["sampling_rate_hz"] = 1.0
    sub.attrs["device"] = "Dexcom G7"
    # Create the timestamps and values datasets that identify this as time-series.
    sub.create_dataset("timestamps", data=np.arange(n, dtype="float64"))
    sub.create_dataset("values", data=np.random.default_rng(42).uniform(70, 180, n))


def _write_data_singlepoint(h5, name="pft"):
    """Create a single-point data entry (e.g., pulmonary function test)."""
    data_grp = h5.require_group("data")
    sub = data_grp.create_group(name)
    # All values stored as attributes — no datasets
    sub.attrs["fev1"] = 2.1
    sub.attrs["fvc"] = 3.4
    sub.attrs["fev1_fvc_ratio"] = 0.62
    sub.attrs["test_date"] = "2026-03-12"


def _write_notes(h5, count=2):
    """Create clinical notes with text datasets."""
    notes_grp = h5.create_group("Notes")  # Capital N, per file spec
    for i in range(1, count + 1):
        sub = notes_grp.create_group(f"note_{i:04d}")  # note_0001, note_0002
        sub.attrs["author"] = f"Dr. Smith_{i}"
        sub.attrs["date"] = f"2026-03-{10 + i:02d}"
        sub.attrs["category"] = "radiology" if i % 2 else "pathology"
        sub.attrs["reviewed"] = True
        # h5py.string_dtype() creates a variable-length UTF-8 string type.
        dt = h5py.string_dtype()
        sub.create_dataset("text", data=f"Sample note content {i}.", dtype=dt)


def _write_chart_review(h5):
    """Create chart review extractions for both human and LLM."""
    cr = h5.create_group("chart_review")

    # --- Human review ---
    human = cr.create_group("human")
    h_note = human.create_group("note_0001")
    h_note.attrs["tumor_size_cm"] = 3.2
    h_note.attrs["location"] = "right upper lobe"
    h_note.attrs["reviewer"] = "Dr. Chen"
    h_note.attrs["review_date"] = "2026-04-15"

    # --- LLM review ---
    llm = cr.create_group("llm")
    l_note = llm.create_group("note_0001")
    l_note.attrs["tumor_size_cm"] = 3.1
    l_note.attrs["location"] = "right upper lobe"
    l_note.attrs["model"] = "claude-opus-4-6"
    l_note.attrs["run_date"] = "2026-04-10"


def _write_genomics(h5):
    """Create genomics metadata with external file paths."""
    gen = h5.create_group("genomics")
    sub = gen.create_group("wgs_2026-07-15")
    sub.attrs["sequencing_platform"] = "Illumina NovaSeq"
    sub.attrs["coverage"] = 30
    sub.attrs["reference_genome"] = "GRCh38"
    sub.attrs["vcf_path"] = "/genomics_archive/P001/variants/"
    sub.attrs["bam_path"] = "/genomics_archive/P001/aligned/"


def _write_changelog(h5):
    """Create the required changelog/ group."""
    cl = h5.create_group("changelog")
    cl.attrs["last_modified"] = "2026-05-10"
    cl.attrs["history"] = np.array(
        ["2026-01-15: created", "2026-03-10: imaging ingested"], dtype="S"
    )


# =========================================================================
# HDF5 FILE FACTORY FIXTURE
# =========================================================================

@pytest.fixture
def tmp_h5(tmp_path):
    """
    A factory fixture that creates spec-compliant .h5 files on demand.

    Usage in a test:
        def test_something(db_conn, tmp_h5):
            path = tmp_h5(patient_id="P042", imaging=True, notes=True)
            # `path` is now a Path to a real .h5 file on disk

    Each call creates a NEW file with a unique name (patient_001.h5,
    patient_002.h5, etc.).  The boolean flags control which sections
    are populated — set them to True to include that data.

    `tmp_path` is a built-in pytest fixture that provides a temporary
    directory.  It's automatically cleaned up after the test.
    """
    # A mutable counter inside a list — lets the inner function increment it.
    # (Python closures can read outer variables but can't reassign them
    #  unless they're mutable objects like lists.)
    counter = [0]

    def _make(
        patient_id: str = "P001",
        demographics: bool = True,
        imaging: bool = False,
        data_ts: bool = False,
        data_sp: bool = False,
        notes: bool = False,
        chart_review: bool = False,
        genomics: bool = False,
    ):
        counter[0] += 1
        path = tmp_path / f"patient_{counter[0]:03d}.h5"

        # Create the HDF5 file in write mode ("w").
        with h5py.File(str(path), "w") as h5:
            # Root attrs and changelog are ALWAYS written (they're required)
            _write_root_attrs(h5, patient_id=patient_id)

            # Optional sections — only written if the flag is True
            if demographics:
                _write_demographics(h5)
            if imaging:
                _write_imaging(h5)
            if data_ts:
                _write_data_timeseries(h5)
            if data_sp:
                _write_data_singlepoint(h5)
            if notes:
                _write_notes(h5)
            if chart_review:
                _write_chart_review(h5)
            if genomics:
                _write_genomics(h5)

            _write_changelog(h5)

        return path

    return _make  # Return the factory function itself (not a file)


@pytest.fixture
def sample_h5_path(tmp_h5):
    """
    A pre-built .h5 file with EVERY section populated.

    Convenient for integration tests that want a "kitchen sink" patient file.
    """
    return tmp_h5(
        imaging=True,
        data_ts=True,
        data_sp=True,
        notes=True,
        chart_review=True,
        genomics=True,
    )
