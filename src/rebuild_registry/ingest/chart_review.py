"""Ingest chart review extractions from chart_review/human/ and chart_review/llm/."""

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
    """Iterate over note_NNNN subgroups within a human/ or llm/ subtree."""
    for name in subtree:
        item = subtree[name]
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"{parent_path}/{name}"

        reviewer = attr(item, "reviewer")
        model = attr(item, "model")
        review_date = attr(item, "review_date") or attr(item, "run_date")
        tumor_size = attr(item, "tumor_size_cm")
        location = attr(item, "location")

        cur.execute(
            """INSERT INTO chart_review
               (patient_id, source_file, group_path, note_name,
                review_source, reviewer, model, review_date,
                tumor_size_cm, location)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, source_file, group_path, name,
                review_source, reviewer, model, review_date,
                tumor_size, location,
            ),
        )


def ingest_chart_review(
    cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str
) -> None:
    """
    Walk ``chart_review/human/note_{NNNN}/`` and ``chart_review/llm/note_{NNNN}/``.
    """
    cr_grp = h5.get("chart_review")
    if cr_grp is None:
        return

    for source_name, review_source in [("human", "human"), ("llm", "llm")]:
        subtree = cr_grp.get(source_name)
        if subtree is not None and isinstance(subtree, h5py.Group):
            _ingest_review_subtree(
                cur, subtree, patient_id, source_file,
                review_source, f"/chart_review/{source_name}",
            )
