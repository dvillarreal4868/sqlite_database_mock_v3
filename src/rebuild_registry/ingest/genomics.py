"""Ingest genomics metadata from the genomics/ group."""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr


def ingest_genomics(
    cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str
) -> None:
    """
    Walk ``genomics/{assay}_{date}/`` subgroups.
    These contain metadata and external file paths only — no heavy data.
    """
    gen_grp = h5.get("genomics")
    if gen_grp is None:
        return

    for name in gen_grp:
        item = gen_grp[name]
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/genomics/{name}"

        # Derive assay name from subgroup name (strip trailing _YYYY-MM-DD)
        parts = name.rsplit("_", 3)
        assay = parts[0] if len(parts) >= 2 else name

        cur.execute(
            """INSERT INTO genomics
               (patient_id, source_file, group_path, assay,
                sequencing_platform, coverage, reference_genome,
                vcf_path, bam_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, source_file, group_path, assay,
                attr(item, "sequencing_platform"),
                attr(item, "coverage"),
                attr(item, "reference_genome"),
                attr(item, "vcf_path"),
                attr(item, "bam_path"),
            ),
        )
