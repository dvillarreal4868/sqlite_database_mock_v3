"""
rebuild_registry/helpers.py

PURPOSE:
    Utility functions for safely reading attributes from HDF5 files.

    HDF5 files store data in a hierarchy (like folders and files), and
    each "group" (folder) or "dataset" (file) can have "attributes" —
    small key-value pairs of metadata attached to them.

    For example, an imaging group might have:
        attrs["modality"]   = "CT"
        attrs["scan_date"]  = "2026-03-10"
        attrs["num_slices"] = 300

    The problem is that HDF5/h5py can store these values in different
    Python/NumPy types:
        - A string might come back as a Python str, or as bytes (b"CT")
        - A number might come back as numpy.int64 instead of plain int
        - A list might come back as a numpy.ndarray

    SQLite (our database) doesn't understand NumPy types.  So these
    helper functions convert everything into plain Python types
    (str, int, float, list) that SQLite can store.

FUNCTIONS:
    attr()           — Read a single attribute (string, number, etc.)
    attr_list()      — Read a list attribute and return it as a JSON string
    shape_str()      — Get a dataset's shape as a string like "(300, 512, 512)"
    all_attrs_json() — Dump ALL attributes on a group into a JSON string
"""

from __future__ import annotations

import json             # For converting Python objects to JSON strings
from typing import Any  # Type hint meaning "any type"

import h5py             # The HDF5 file reading library
import numpy as np      # NumPy — used by h5py for numeric types


def attr(obj: h5py.Group | h5py.Dataset, key: str, default: Any = None) -> Any:
    """
    Read a single attribute from an HDF5 group or dataset, converting
    it to a plain Python type.

    Parameters
    ----------
    obj : h5py.Group or h5py.Dataset
        The HDF5 object to read from (e.g., a group like h5["imaging/ct_2026-03-10"])
    key : str
        The attribute name (e.g., "modality", "scan_date")
    default : any, optional
        What to return if the attribute doesn't exist.  Defaults to None.

    Returns
    -------
    The attribute value as a plain Python type, or `default` if not found.

    Examples
    --------
    # If the imaging group has attrs["modality"] = "CT":
    >>> attr(imaging_group, "modality")
    "CT"

    # If the attribute doesn't exist:
    >>> attr(imaging_group, "nonexistent")
    None

    # If the attribute is stored as bytes (common in HDF5):
    # h5py sometimes stores "CT" as b"CT"
    >>> attr(imaging_group, "modality")
    "CT"  # We decode it automatically
    """
    # .attrs is a dictionary-like object on every HDF5 group/dataset.
    # .get(key, default) returns the value if it exists, or `default` if not.
    val = obj.attrs.get(key, default)

    # HDF5 sometimes stores strings as raw bytes (e.g., b"CT" instead of "CT").
    # We decode them back to regular Python strings.
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")

    # HDF5/NumPy stores numbers as numpy types (e.g., numpy.int64(300)).
    # SQLite doesn't understand these, so we convert to plain Python types.
    # numpy.generic is the base class for all NumPy scalar types.
    # .item() converts numpy.int64(300) → 300, numpy.float64(2.1) → 2.1
    if isinstance(val, np.generic):
        return val.item()

    # If it's already a plain Python type (str, int, float), return as-is.
    return val


def attr_list(obj: h5py.Group | h5py.Dataset, key: str) -> str | None:
    """
    Read a list-like attribute and return it as a JSON string.

    HDF5 stores lists (like tags or IRB lists) as NumPy arrays.
    SQLite doesn't have an "array" column type, so we serialize the
    list to a JSON string for storage.

    Parameters
    ----------
    obj : h5py.Group or h5py.Dataset
        The HDF5 object to read from.
    key : str
        The attribute name.

    Returns
    -------
    str or None
        A JSON string like '["lung_ca", "smoker"]', or None if the
        attribute doesn't exist.

    Examples
    --------
    # If root attrs has tags = ["lung_ca", "smoker"]:
    >>> attr_list(h5_file, "tags")
    '["lung_ca", "smoker"]'

    # If the attribute doesn't exist:
    >>> attr_list(h5_file, "nonexistent")
    None
    """
    val = obj.attrs.get(key, None)

    # Attribute doesn't exist — return None
    if val is None:
        return None

    # Most common case: h5py returns a numpy array of bytes or strings
    if isinstance(val, np.ndarray):
        items = []
        for v in val:
            if isinstance(v, bytes):
                # Decode bytes to string: b"lung_ca" → "lung_ca"
                items.append(v.decode("utf-8", errors="replace"))
            elif isinstance(v, np.generic):
                # Convert numpy scalar to Python: numpy.float64(0.5) → 0.5
                items.append(v.item())
            else:
                items.append(v)
        # json.dumps converts a Python list to a JSON string:
        # ["lung_ca", "smoker"] → '["lung_ca", "smoker"]'
        return json.dumps(items)

    # Less common: already a Python list or tuple
    if isinstance(val, (list, tuple)):
        return json.dumps([
            v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
            for v in val
        ])

    # Edge case: a single value that should be treated as a 1-element list
    return json.dumps([val])


def shape_str(ds: h5py.Dataset) -> str:
    """
    Return a dataset's shape as a human-readable string.

    HDF5 datasets (like imaging volumes) have a `.shape` property,
    similar to NumPy arrays.  We store this as a string in the database
    so you can see at a glance what size the volume is.

    Parameters
    ----------
    ds : h5py.Dataset
        The dataset to get the shape of.

    Returns
    -------
    str
        Shape as a string, e.g. "(300, 512, 512)"
    """
    return str(ds.shape)


def all_attrs_json(grp: h5py.Group) -> str:
    """
    Serialize ALL attributes on a group into a single JSON string.

    This is used for single-point measurement data (like PFT results)
    where the values are stored as individual attributes rather than
    datasets.  Instead of creating a column for every possible attribute,
    we dump them all into one JSON blob.

    Parameters
    ----------
    grp : h5py.Group
        The HDF5 group whose attributes to serialize.

    Returns
    -------
    str
        A JSON string like '{"fev1": 2.1, "fvc": 3.4, "test_date": "2026-03-12"}'

    Example
    -------
    # If data/pft/ has attrs: fev1=2.1, fvc=3.4, fev1_fvc_ratio=0.62
    >>> all_attrs_json(h5["data/pft"])
    '{"fev1": 2.1, "fvc": 3.4, "fev1_fvc_ratio": 0.62}'
    """
    out: dict[str, Any] = {}

    # Iterate over every attribute on the group
    for k, v in grp.attrs.items():
        if isinstance(v, bytes):
            out[k] = v.decode("utf-8", errors="replace")
        elif isinstance(v, np.generic):
            out[k] = v.item()               # numpy scalar → Python scalar
        elif isinstance(v, np.ndarray):
            out[k] = v.tolist()             # numpy array → Python list
        else:
            out[k] = v                      # already a Python type

    return json.dumps(out)
