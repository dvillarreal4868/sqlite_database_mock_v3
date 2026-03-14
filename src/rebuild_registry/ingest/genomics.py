"""
rebuild_registry/ingest/genomics.py

PURPOSE:
    Reads genomics metadata from the HDF5 file's genomics/ group and
    inserts one row per assay into the `genomics` table.

WHERE THE DATA COMES FROM IN THE .h5 FILE:
    genomics/
    └── wgs_2026-07-15/
        └── [attrs: sequencing_platform="Illumina NovaSeq",
                     coverage=30,
                     reference_genome="GRCh38",
                     vcf_path="/genomics_archive/P001/variants/",
                     bam_path="/genomics_archive/P001/aligned/"]

    Each subgroup is named {assay}_{date}, e.g. "wgs_2026-07-15".

IMPORTANT:
    The actual genomic data (VCF files, BAM files) is NOT stored in the
    .h5 file — it's too large.  The .h5 file only stores metadata and
    paths pointing to where the data lives on disk.  We record those
    paths in the registry so you can find the data later.
"""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr


def ingest_genomics(
    cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str
) -> None:
    """
    Walk the genomics/ group and insert one row per assay.

    Parameters
    ----------
    cur : sqlite3.Cursor
        Database cursor.
    h5 : h5py.File
        An open HDF5 file.
    patient_id : str
        The patient ID.
    source_file : str
        Relative path to the .h5 file.
    """

    # --- Check if genomics/ group exists ---
    gen_grp = h5.get("genomics")
    if gen_grp is None:
        return  # No genomics data for this patient

    # --- Loop over each assay subgroup ---
    for name in gen_grp:
        item = gen_grp[name]

        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/genomics/{name}"  # e.g., "/genomics/wgs_2026-07-15"

        # --- Derive the assay name from the subgroup name ---
        # The subgroup name is "{assay}_{YYYY-MM-DD}", e.g. "wgs_2026-07-15".
        # We want just the assay part: "wgs".
        #
        # rsplit("_", 3) splits from the RIGHT, up to 3 times:
        #   "wgs_2026-07-15".rsplit("_", 3) = ["wgs", "2026", "07", "15"]
        # Then parts[0] gives us "wgs".
        #
        # If there are no underscores, we just use the full name.
        parts = name.rsplit("_", 3)
        assay = parts[0] if len(parts) >= 2 else name

        # --- Insert a row ---
        cur.execute(
            """INSERT INTO genomics
               (patient_id, source_file, group_path, assay,
                sequencing_platform, coverage, reference_genome,
                vcf_path, bam_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id,
                source_file,
                group_path,
                assay,                                    # e.g., "wgs"
                attr(item, "sequencing_platform"),        # "Illumina NovaSeq"
                attr(item, "coverage"),                   # 30
                attr(item, "reference_genome"),           # "GRCh38"
                attr(item, "vcf_path"),                   # external file path
                attr(item, "bam_path"),                   # external file path
            ),
        )
