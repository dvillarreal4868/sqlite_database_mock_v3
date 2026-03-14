"""Ingest structured data entries from the data/ group."""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr, all_attrs_json


def _is_timeseries(grp: h5py.Group) -> bool:
    """A data subgroup is time-series if it contains timestamps + values datasets."""
    return "timestamps" in grp and "values" in grp


def ingest_data(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk ``data/{data_type}/`` subgroups.

    * **Time-series** entries (contain ``timestamps`` and ``values`` datasets)
      get ``is_timeseries=1`` with sample count, sampling rate, etc.
    * **Single-point** entries get ``is_timeseries=0`` with all group attributes
      dumped into ``attributes_json``.
    """
    data_grp = h5.get("data")
    if data_grp is None:
        return

    for name in data_grp:
        item = data_grp[name]
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/data/{name}"
        timeseries = _is_timeseries(item)

        session_date = attr(item, "session_date") or attr(item, "test_date")
        sampling_rate = attr(item, "sampling_rate_hz")
        device = attr(item, "device")
        num_samples = None
        attrs_json = None

        if timeseries:
            ts_ds = item["timestamps"]
            if isinstance(ts_ds, h5py.Dataset) and len(ts_ds.shape) >= 1:
                num_samples = ts_ds.shape[0]
        else:
            attrs_json = all_attrs_json(item)

        cur.execute(
            """INSERT INTO data_entries
               (patient_id, source_file, group_path, data_type, is_timeseries,
                session_date, sampling_rate_hz, device, num_samples, attributes_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, source_file, group_path, name, int(timeseries),
                session_date, sampling_rate, device, num_samples, attrs_json,
            ),
        )
