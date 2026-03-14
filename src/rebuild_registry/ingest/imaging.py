"""
rebuild_registry/ingest/imaging.py

PURPOSE:
    Reads imaging session metadata from the HDF5 file's imaging/ group
    and inserts one row per session into the `imaging` table.

WHERE THE DATA COMES FROM IN THE .h5 FILE:
    imaging/
    ├── ct_2026-03-10/
    │   ├── volume          (dataset: the actual 3D image, shape like [300, 512, 512])
    │   └── [attrs: modality="CT", scan_date="2026-03-10", num_slices=300, ...]
    └── mri_2026-05-15/
        ├── volume          (dataset)
        └── [attrs: modality="MRI", scan_date="2026-05-15", ...]

    Each subgroup under imaging/ represents one scan session.
    The subgroup name follows the pattern: {modality}_{date}

IMPORTANT:
    We NEVER load the actual volume data into memory.  The volume datasets
    can be hundreds of megabytes.  We only read:
      - The attributes (small metadata like modality, scan_date)
      - The shape of the volume dataset (e.g., (300, 512, 512))
    This is what makes the registry rebuild fast.
"""

from __future__ import annotations

import sqlite3

import h5py

# Go up one directory (..) from ingest/ to rebuild_registry/, then import from helpers.py
from ..helpers import attr, attr_list, shape_str


def ingest_imaging(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk the imaging/ group and insert one row per scan session.

    Parameters
    ----------
    cur : sqlite3.Cursor
        Database cursor for executing SQL.
    h5 : h5py.File
        An open HDF5 file.
    patient_id : str
        The patient ID (e.g., "P001") — used for the foreign key.
    source_file : str
        Relative path to the .h5 file, stored for reference.
    """

    # --- Check if imaging/ group exists ---
    # h5.get("imaging") returns the group object if it exists, or None.
    # Many patients won't have imaging data, so we just return silently.
    imaging_grp = h5.get("imaging")
    if imaging_grp is None:
        return  # No imaging data for this patient — that's fine

    # --- Loop over each subgroup (each scan session) ---
    # `imaging_grp` acts like a dictionary.  Iterating gives us the names
    # of everything inside it (e.g., "ct_2026-03-10", "mri_2026-05-15").
    for name in imaging_grp:
        item = imaging_grp[name]

        # Skip anything that isn't a group (subgroups represent sessions).
        # There shouldn't be stray datasets at this level, but be safe.
        if not isinstance(item, h5py.Group):
            continue

        # The HDF5 path for this session (stored in the DB for traceability).
        # Example: "/imaging/ct_2026-03-10"
        group_path = f"/imaging/{name}"

        # --- Read the session's attributes ---
        modality = attr(item, "modality")         # "CT", "MRI", etc.
        scan_date = attr(item, "scan_date")       # "2026-03-10"
        num_slices = attr(item, "num_slices")     # 300
        voxel_spacing = attr_list(item, "voxel_spacing_mm")  # '[0.5, 0.5, 1.0]'
        body_region = attr(item, "body_region")   # "chest"
        source_irb = attr(item, "source_irb")     # "IRB-2025-001"

        # --- Read the volume dataset's shape WITHOUT loading data ---
        # We check: does a dataset called "volume" exist in this group?
        # If so, we read its .shape property (which is free — no data loaded).
        volume_shape = None
        if "volume" in item and isinstance(item["volume"], h5py.Dataset):
            volume_shape = shape_str(item["volume"])  # e.g., "(300, 512, 512)"

            # If num_slices wasn't set as an attribute, we can infer it
            # from the first dimension of the volume shape.
            if num_slices is None and len(item["volume"].shape) >= 1:
                num_slices = item["volume"].shape[0]  # e.g., 300

        # --- Insert a row into the imaging table ---
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
