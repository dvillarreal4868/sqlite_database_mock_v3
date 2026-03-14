"""Ingest clinical notes from the Notes/ group."""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr


def ingest_notes(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk ``Notes/note_{NNNN}/`` subgroups.
    Reads attributes and the length of the ``text`` dataset (without loading content).
    """
    notes_grp = h5.get("Notes")
    if notes_grp is None:
        return

    for name in notes_grp:
        item = notes_grp[name]
        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/Notes/{name}"
        author = attr(item, "author")
        date = attr(item, "date")
        category = attr(item, "category")
        reviewed_raw = attr(item, "reviewed")
        reviewed = int(bool(reviewed_raw)) if reviewed_raw is not None else None

        # Get character length from the text dataset without reading the content
        char_length = None
        if "text" in item and isinstance(item["text"], h5py.Dataset):
            ds = item["text"]
            if ds.shape == ():
                char_length = len(ds[()])
            elif len(ds.shape) >= 1:
                char_length = ds.shape[0]

        cur.execute(
            """INSERT INTO notes
               (patient_id, source_file, group_path, note_name,
                author, date, category, reviewed, char_length)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id, source_file, group_path, name,
                author, date, category, reviewed, char_length,
            ),
        )
