"""
rebuild_registry/ingest/notes.py

PURPOSE:
    Reads clinical notes from the HDF5 file's Notes/ group and inserts
    one row per note into the `notes` table.

WHERE THE DATA COMES FROM IN THE .h5 FILE:
    Notes/
    ├── note_0001/
    │   ├── text          (dataset: the full note text as a string)
    │   └── [attrs: author="Dr. Smith", date="2026-03-10",
    │                category="radiology", reviewed=true]
    └── note_0002/
        ├── text          (dataset)
        └── [attrs: ...]

    Note the CAPITAL "N" in "Notes/" — this matches the file spec exactly.
    HDF5 group names are case-sensitive.

WHAT WE STORE:
    We do NOT store the full note text in the registry.  The note text
    could be thousands of characters and we'd be duplicating data that
    already lives in the .h5 file.  Instead, we store:
      - The metadata (author, date, category, reviewed status)
      - The character length of the text (so you can search for long/short notes)
"""

from __future__ import annotations

import sqlite3

import h5py

from ..helpers import attr


def ingest_notes(cur: sqlite3.Cursor, h5: h5py.File, patient_id: str, source_file: str) -> None:
    """
    Walk the Notes/ group and insert one row per clinical note.

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

    # --- Check if Notes/ group exists ---
    # Note the capital "N" — must match the file spec exactly.
    notes_grp = h5.get("Notes")
    if notes_grp is None:
        return  # No clinical notes for this patient

    # --- Loop over each note subgroup ---
    for name in notes_grp:
        item = notes_grp[name]

        if not isinstance(item, h5py.Group):
            continue

        group_path = f"/Notes/{name}"  # e.g., "/Notes/note_0001"

        # --- Read note attributes ---
        author = attr(item, "author")       # "Dr. Smith"
        date = attr(item, "date")           # "2026-03-10"
        category = attr(item, "category")   # "radiology", "pathology", "general"

        # --- Handle the "reviewed" boolean ---
        # HDF5 stores booleans in various ways (True, 1, numpy.bool_(True)).
        # SQLite doesn't have a boolean type, so we convert to INTEGER:
        #   True  → 1
        #   False → 0
        #   None  → None (if the attribute doesn't exist)
        reviewed_raw = attr(item, "reviewed")
        reviewed = int(bool(reviewed_raw)) if reviewed_raw is not None else None

        # --- Get the character length of the note text ---
        # We read the shape/length of the text dataset WITHOUT reading the
        # actual text content.  This tells us how long the note is.
        char_length = None
        if "text" in item and isinstance(item["text"], h5py.Dataset):
            ds = item["text"]

            # HDF5 variable-length string datasets can be:
            # - Scalar (shape = ()): a single string → read it and take len()
            # - 1-D array (shape = (N,)): an array of strings → N is the count
            #
            # For our use case (one note = one string), it's typically scalar.
            if ds.shape == ():
                # Scalar string dataset — we have to read it to get the length.
                # ds[()] reads a scalar dataset's value.
                char_length = len(ds[()])
            elif len(ds.shape) >= 1:
                # Array of strings — the shape tells us how many strings
                char_length = ds.shape[0]

        # --- Insert a row ---
        cur.execute(
            """INSERT INTO notes
               (patient_id, source_file, group_path, note_name,
                author, date, category, reviewed, char_length)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id,
                source_file,
                group_path,
                name,           # note_name, e.g. "note_0001"
                author,
                date,
                category,
                reviewed,       # 0, 1, or None
                char_length,
            ),
        )
