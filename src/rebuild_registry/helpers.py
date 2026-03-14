"""
rebuild_registry.helpers
~~~~~~~~~~~~~~~~~~~~~~~~
Utilities for safely reading HDF5 attributes and dataset metadata.
"""

from __future__ import annotations

import json
from typing import Any

import h5py
import numpy as np


def attr(obj: h5py.Group | h5py.Dataset, key: str, default: Any = None) -> Any:
    """Read a scalar attribute, decoding bytes→str and numpy scalars→Python."""
    val = obj.attrs.get(key, default)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, np.generic):
        return val.item()
    return val


def attr_list(obj: h5py.Group | h5py.Dataset, key: str) -> str | None:
    """Read a list-like attribute and return it as a JSON string, or None."""
    val = obj.attrs.get(key, None)
    if val is None:
        return None
    if isinstance(val, np.ndarray):
        items = []
        for v in val:
            if isinstance(v, bytes):
                items.append(v.decode("utf-8", errors="replace"))
            elif isinstance(v, np.generic):
                items.append(v.item())
            else:
                items.append(v)
        return json.dumps(items)
    if isinstance(val, (list, tuple)):
        return json.dumps([
            v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
            for v in val
        ])
    return json.dumps([val])


def shape_str(ds: h5py.Dataset) -> str:
    """Return dataset shape as a string like '(300, 512, 512)'."""
    return str(ds.shape)


def all_attrs_json(grp: h5py.Group) -> str:
    """Serialize every attribute on *grp* to a JSON dict string."""
    out: dict[str, Any] = {}
    for k, v in grp.attrs.items():
        if isinstance(v, bytes):
            out[k] = v.decode("utf-8", errors="replace")
        elif isinstance(v, np.generic):
            out[k] = v.item()
        elif isinstance(v, np.ndarray):
            out[k] = v.tolist()
        else:
            out[k] = v
    return json.dumps(out)
