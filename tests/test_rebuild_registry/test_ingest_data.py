"""Tests for rebuild_registry.ingest.data — timeseries and single-point entries."""

import json

import h5py

from rebuild_registry.ingest.patients import ingest_patient
from rebuild_registry.ingest.data import ingest_data


def _setup_patient(db_conn, h5, source="archive/p.h5"):
    cur = db_conn.cursor()
    pid = ingest_patient(cur, h5, source)
    db_conn.commit()
    return cur, pid


class TestIngestTimeseries:
    def test_glucose_timeseries(self, db_conn, tmp_h5):
        path = tmp_h5(data_ts=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_data(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT data_type, is_timeseries, session_date, sampling_rate_hz, "
            "device, num_samples, attributes_json FROM data_entries"
        ).fetchone()
        dtype, is_ts, sdate, rate, device, nsamples, attrs_j = row

        assert dtype == "glucose"
        assert is_ts == 1
        assert sdate == "2026-03-10"
        assert rate == 1.0
        assert device == "Dexcom G7"
        assert nsamples == 100
        assert attrs_j is None

    def test_no_data_group(self, db_conn, tmp_h5):
        path = tmp_h5(data_ts=False, data_sp=False)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_data(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM data_entries").fetchone()[0]
        assert count == 0


class TestIngestSinglePoint:
    def test_pft_singlepoint(self, db_conn, tmp_h5):
        path = tmp_h5(data_sp=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_data(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        row = cur.execute(
            "SELECT data_type, is_timeseries, session_date, attributes_json "
            "FROM data_entries"
        ).fetchone()
        dtype, is_ts, sdate, attrs_j = row

        assert dtype == "pft"
        assert is_ts == 0
        assert sdate == "2026-03-12"
        parsed = json.loads(attrs_j)
        assert abs(parsed["fev1"] - 2.1) < 0.01
        assert abs(parsed["fvc"] - 3.4) < 0.01

    def test_both_types_together(self, db_conn, tmp_h5):
        path = tmp_h5(data_ts=True, data_sp=True)
        with h5py.File(str(path), "r") as h5:
            cur, pid = _setup_patient(db_conn, h5)
            ingest_data(cur, h5, pid, "archive/p.h5")
        db_conn.commit()

        count = cur.execute("SELECT COUNT(*) FROM data_entries").fetchone()[0]
        assert count == 2

        ts_row = cur.execute(
            "SELECT is_timeseries FROM data_entries WHERE data_type='glucose'"
        ).fetchone()
        sp_row = cur.execute(
            "SELECT is_timeseries FROM data_entries WHERE data_type='pft'"
        ).fetchone()
        assert ts_row[0] == 1
        assert sp_row[0] == 0
