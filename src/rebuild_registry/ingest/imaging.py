"""Ingest imaging sessions from the imaging/ group."""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr, attr_list, shape_str


def ingest_imaging(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk ``imaging/{modality}_{date}/`` subgroups.
    Reads attributes and the shape of the ``volume`` dataset (without loading data).
    """
    imaging_grp = h5.get("imaging")
    if imaging_grp is None:
        return

    for name in imaging_grp:
        item = imaging_grp[name]
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/imaging/{name}"
        modality = attr(item, "modality")
        scan_date = attr(item, "scan_date")
        num_slices = attr(item, "num_slices")
        voxel_spacing = attr_list(item, "voxel_spacing_mm")
        body_region = attr(item, "body_region")
        source_irb = attr(item, "source_irb")

        # Read volume dataset shape without loading data
        volume_shape = None
        if "volume" in item and isinstance(item["volume"], h5py.Dataset):
            volume_shape = shape_str(item["volume"])
            if num_slices is None and len(item["volume"].shape) >= 1:
                num_slices = item["volume"].shape[0]

        cur.execute(
            """INSERT INTO imaging
               (patient_id, source_file, group_path, modality, scan_date,
                num_slices, voxel_spacing_mm, body_region, source_irb, volume_shape)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, source_file, group_path, modality, scan_date,
                num_slices, voxel_spacing, body_region, source_irb, volume_shape,
            ),
        )
