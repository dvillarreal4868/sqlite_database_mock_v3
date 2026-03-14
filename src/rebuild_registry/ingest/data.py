"""
rebuild_registry/ingest/data.py

PURPOSE:
    Reads structured data entries from the HDF5 file's data/ group and
    inserts one row per entry into the `data_entries` table.

    The data/ group can contain two kinds of entries:

    1. TIME-SERIES data (e.g., continuous glucose monitoring)
       These have `timestamps` and `values` datasets inside them.
       Example:
           data/glucose/
           ├── timestamps   (dataset: [0.0, 1.0, 2.0, ...])
           ├── values        (dataset: [95.0, 102.0, 98.0, ...])
           └── [attrs: session_date="2026-03-10", sampling_rate_hz=1.0, device="Dexcom G7"]

    2. SINGLE-POINT measurements (e.g., pulmonary function test results)
       These have NO datasets — all values are stored as attributes.
       Example:
           data/pft/
           └── [attrs: fev1=2.1, fvc=3.4, fev1_fvc_ratio=0.62, test_date="2026-03-12"]

    We distinguish between them by checking whether the group contains
    both `timestamps` and `values` datasets.
"""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr, all_attrs_json


def _is_timeseries(grp: h5py.Group) -> bool:
    """
    Determine if a data subgroup is a time-series.

    A group is considered time-series if it contains both a `timestamps`
    dataset and a `values` dataset (per the file spec).

    Returns True for time-series, False for single-point measurements.
    """
    return "timestamps" in grp and "values" in grp


def ingest_data(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk the data/ group and insert one row per data type.

    Parameters
    ----------
    cur : sqlite3.Cursor
        Database cursor for executing SQL.
    h5 : h5py.File
        An open HDF5 file.
    patient_id : str
        The patient ID (e.g., "P001").
    source_file : str
        Relative path to the .h5 file.
    """

    # --- Check if data/ group exists ---
    data_grp = h5.get("data")
    if data_grp is None:
        return  # No structured data for this patient

    # --- Loop over each data type subgroup ---
    # Each child of data/ is named by its type: "glucose", "pft", etc.
    for name in data_grp:
        item = data_grp[name]

        # Skip non-groups
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/data/{name}"  # e.g., "/data/glucose"

        # --- Determine if this is time-series or single-point ---
        timeseries = _is_timeseries(item)

        # --- Read common attributes ---
        # Time-series entries use "session_date", single-point entries
        # use "test_date".  We try both.  The `or` means: if the first
        # one returns None, try the second one.
        session_date = attr(item, "session_date") or attr(item, "test_date")
        sampling_rate = attr(item, "sampling_rate_hz")  # Hz (time-series only)
        device = attr(item, "device")                   # device name (time-series only)

        # These will be filled differently depending on the type
        num_samples = None
        attrs_json = None

        if timeseries:
            # --- Time-series: count the samples ---
            # We read the shape of the timestamps dataset to know how
            # many data points there are, WITHOUT loading the actual data.
            ts_ds = item["timestamps"]
            if isinstance(ts_ds, h5py.Dataset) and len(ts_ds.shape) >= 1:
                num_samples = ts_ds.shape[0]  # e.g., 1440 samples
        else:
            # --- Single-point: dump all attributes to JSON ---
            # For single-point measurements like PFTs, the actual values
            # (fev1, fvc, etc.) are stored as attributes.  We serialize
            # them all into one JSON string so we don't need a column
            # for every possible measurement type.
            attrs_json = all_attrs_json(item)
            # Example: '{"fev1": 2.1, "fvc": 3.4, "test_date": "2026-03-12"}'

        # --- Insert a row ---
        cur.execute(
            """INSERT INTO data_entries
               (patient_id, source_file, group_path, data_type, is_timeseries,
                session_date, sampling_rate_hz, device, num_samples, attributes_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id,
                source_file,
                group_path,
                name,               # data_type, e.g. "glucose" or "pft"
                int(timeseries),    # 1 for time-series, 0 for single-point
                session_date,
                sampling_rate,
                device,
                num_samples,        # filled for time-series, None for single-point
                attrs_json,         # filled for single-point, None for time-series
            ),
        )
