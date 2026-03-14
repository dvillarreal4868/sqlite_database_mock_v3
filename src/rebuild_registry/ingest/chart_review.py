"""
rebuild_registry/ingest/chart_review.py

PURPOSE:
    Reads chart review extractions from the HDF5 file's chart_review/ group
    and inserts one row per extraction into the `chart_review` table.

WHERE THE DATA COMES FROM IN THE .h5 FILE:
    chart_review/
    ├── human/                        ← extractions done by human reviewers
    │   └── note_0001/
    │       └── [attrs: tumor_size_cm=3.2, location="right upper lobe",
    │                    reviewer="Dr. Chen", review_date="2026-04-15"]
    └── llm/                          ← extractions done by LLM models
        └── note_0001/
            └── [attrs: tumor_size_cm=3.1, location="right upper lobe",
                         model="claude-opus-4-6", run_date="2026-04-10"]

    The chart_review/ group has TWO subtrees: human/ and llm/.
    Each subtree contains note_NNNN/ subgroups that mirror the notes
    in Notes/.  The note_NNNN name tells you WHICH note was reviewed.

    Human reviews have `reviewer` + `review_date` attributes.
    LLM reviews have `model` + `run_date` attributes instead.

    Both types can have extraction fields like `tumor_size_cm` and `location`.
"""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr


def _ingest_review_subtree(
    cur: sqlite3.Cursor,
    subtree: h5py.Group,
    patient_id: str,
    source_file: str,
    review_source: str,
    parent_path: str,
) -> None:
    """
    Process all note_NNNN subgroups within either the human/ or llm/ subtree.

    This is a helper function called twice by ingest_chart_review():
    once for the human/ subtree and once for the llm/ subtree.

    Parameters
    ----------
    cur : sqlite3.Cursor
        Database cursor.
    subtree : h5py.Group
        The human/ or llm/ HDF5 group.
    patient_id : str
        The patient ID.
    source_file : str
        Relative path to the .h5 file.
    review_source : str
        Either "human" or "llm" — stored in the review_source column.
    parent_path : str
        The HDF5 path prefix, e.g. "/chart_review/human"
    """
    for name in subtree:
        item = subtree[name]

        if not isinstance(item, h5py.Group):
            continue

        # Full HDF5 path, e.g. "/chart_review/human/note_0001"
        group_path = f"{parent_path}/{name}"

        # --- Read attributes ---
        # Human reviews have "reviewer" and "review_date".
        # LLM reviews have "model" and "run_date".
        # We read all four — the irrelevant ones will just be None.
        reviewer = attr(item, "reviewer")       # "Dr. Chen" or None (for LLM)
        model = attr(item, "model")             # "claude-opus-4-6" or None (for human)

        # Both types have a date, but under different attribute names.
        # The `or` tries review_date first, then falls back to run_date.
        review_date = attr(item, "review_date") or attr(item, "run_date")

        # --- Read extracted fields ---
        tumor_size = attr(item, "tumor_size_cm")   # e.g., 3.2
        location = attr(item, "location")           # e.g., "right upper lobe"

        # --- Insert a row ---
        cur.execute(
            """INSERT INTO chart_review
               (patient_id, source_file, group_path, note_name,
                review_source, reviewer, model, review_date,
                tumor_size_cm, location)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id,
                source_file,
                group_path,
                name,               # note_name, e.g. "note_0001"
                review_source,      # "human" or "llm"
                reviewer,           # filled for human, None for llm
                model,              # filled for llm, None for human
                review_date,
                tumor_size,
                location,
            ),
        )


def ingest_chart_review(
    cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str
) -> None:
    """
    Walk chart_review/human/ and chart_review/llm/ and insert one row
    per review extraction.

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

    # --- Check if chart_review/ group exists ---
    cr_grp = h5.get("chart_review")
    if cr_grp is None:
        return  # No chart reviews for this patient

    # --- Process each subtree (human and llm) ---
    # We iterate over a list of (subtree_name, label) pairs.
    # If a subtree doesn't exist (e.g., no LLM reviews yet), we skip it.
    for source_name, review_source in [("human", "human"), ("llm", "llm")]:

        # Try to get the subtree group.
        # Example: cr_grp.get("human") returns the human/ group or None.
        subtree = cr_grp.get(source_name)

        if subtree is not None and isinstance(subtree, h5py.Group):
            _ingest_review_subtree(
                cur,
                subtree,
                patient_id,
                source_file,
                review_source,                      # "human" or "llm"
                f"/chart_review/{source_name}",     # path prefix
            )
