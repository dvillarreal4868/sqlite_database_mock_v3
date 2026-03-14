"""
conftest.py — shared fixtures for rebuild_registry tests.

Provides:
  - db_conn:        a fresh in-memory SQLite connection with the full schema
  - tmp_h5:         a factory that creates a spec-compliant .h5 file in a tmpdir
  - sample_h5_path: a fully-populated sample patient file ready for ingest tests
"""

from __future__ import annotations

import sqlite3

import h5py
import numpy as np
import pytest

from rebuild_registry.schema import SCHEMA_SQL


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn():
    """Yield a fresh in-memory SQLite connection with the registry schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.cursor().executescript(SCHEMA_SQL)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# HDF5 builder helpers
# ---------------------------------------------------------------------------

def _write_root_attrs(h5, patient_id="P001"):
    h5.attrs["patient_id"] = patient_id
    h5.attrs["tags"] = np.array(["lung_ca", "smoker"], dtype="S")
    h5.attrs["active_irbs"] = np.array(["IRB-2025-001"], dtype="S")
    h5.attrs["irb_history"] = np.array(["IRB-2024-010"], dtype="S")
    h5.attrs["created_date"] = "2026-01-15"


def _write_demographics(h5, age=64, sex="M", diagnosis="NSCLC", staging="Stage III"):
    grp = h5.create_group("demographics")
    grp.attrs["age"] = age
    grp.attrs["sex"] = sex
    grp.attrs["diagnosis"] = diagnosis
    grp.attrs["staging"] = staging


def _write_imaging(h5, modality="CT", date="2026-03-10", shape=(10, 512, 512)):
    img_grp = h5.require_group("imaging")
    sub = img_grp.create_group(f"{modality.lower()}_{date}")
    sub.attrs["modality"] = modality
    sub.attrs["scan_date"] = date
    sub.attrs["num_slices"] = shape[0]
    sub.attrs["voxel_spacing_mm"] = np.array([0.5, 0.5, 1.0])
    sub.attrs["body_region"] = "chest"
    sub.attrs["source_irb"] = "IRB-2025-001"
    sub.create_dataset("volume", shape=shape, dtype="int16")


def _write_data_timeseries(h5, name="glucose", n=100):
    data_grp = h5.require_group("data")
    sub = data_grp.create_group(name)
    sub.attrs["session_date"] = "2026-03-10"
    sub.attrs["sampling_rate_hz"] = 1.0
    sub.attrs["device"] = "Dexcom G7"
    sub.create_dataset("timestamps", data=np.arange(n, dtype="float64"))
    sub.create_dataset("values", data=np.random.default_rng(42).uniform(70, 180, n))


def _write_data_singlepoint(h5, name="pft"):
    data_grp = h5.require_group("data")
    sub = data_grp.create_group(name)
    sub.attrs["fev1"] = 2.1
    sub.attrs["fvc"] = 3.4
    sub.attrs["fev1_fvc_ratio"] = 0.62
    sub.attrs["test_date"] = "2026-03-12"


def _write_notes(h5, count=2):
    notes_grp = h5.create_group("Notes")
    for i in range(1, count + 1):
        sub = notes_grp.create_group(f"note_{i:04d}")
        sub.attrs["author"] = f"Dr. Smith_{i}"
        sub.attrs["date"] = f"2026-03-{10 + i:02d}"
        sub.attrs["category"] = "radiology" if i % 2 else "pathology"
        sub.attrs["reviewed"] = True
        dt = h5py.string_dtype()
        sub.create_dataset("text", data=f"Sample note content {i}.", dtype=dt)


def _write_chart_review(h5):
    cr = h5.create_group("chart_review")
    human = cr.create_group("human")
    h_note = human.create_group("note_0001")
    h_note.attrs["tumor_size_cm"] = 3.2
    h_note.attrs["location"] = "right upper lobe"
    h_note.attrs["reviewer"] = "Dr. Chen"
    h_note.attrs["review_date"] = "2026-04-15"

    llm = cr.create_group("llm")
    l_note = llm.create_group("note_0001")
    l_note.attrs["tumor_size_cm"] = 3.1
    l_note.attrs["location"] = "right upper lobe"
    l_note.attrs["model"] = "claude-opus-4-6"
    l_note.attrs["run_date"] = "2026-04-10"


def _write_genomics(h5):
    gen = h5.create_group("genomics")
    sub = gen.create_group("wgs_2026-07-15")
    sub.attrs["sequencing_platform"] = "Illumina NovaSeq"
    sub.attrs["coverage"] = 30
    sub.attrs["reference_genome"] = "GRCh38"
    sub.attrs["vcf_path"] = "/genomics_archive/P001/variants/"
    sub.attrs["bam_path"] = "/genomics_archive/P001/aligned/"


def _write_changelog(h5):
    cl = h5.create_group("changelog")
    cl.attrs["last_modified"] = "2026-05-10"
    cl.attrs["history"] = np.array(
        ["2026-01-15: created", "2026-03-10: imaging ingested"], dtype="S"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_h5(tmp_path):
    """
    Factory fixture.  Call it to get a path to a new .h5 file.

    Usage in a test::

        path = tmp_h5(imaging=True, notes=True)
    """
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
        with h5py.File(str(path), "w") as h5:
            _write_root_attrs(h5, patient_id=patient_id)
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

    return _make


@pytest.fixture
def sample_h5_path(tmp_h5):
    """A fully-populated sample patient file with every group present."""
    return tmp_h5(
        imaging=True,
        data_ts=True,
        data_sp=True,
        notes=True,
        chart_review=True,
        genomics=True,
    )
