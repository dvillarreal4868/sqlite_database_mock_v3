"""
validate/helpers.py

PURPOSE:
    This module provides reusable utility functions for interacting with
    HDF5 (.h5) files and performing validation checks.

    These are "atomic" functions — each one does exactly ONE thing,
    like checking if an attribute exists, checking its data type,
    or verifying a group's presence.

BENEFITS:
    - Consistency: Every part of the validator uses the same logic.
    - Readability: Rules (in rules.py) can call `check_attribute()`
      instead of repeating low-level HDF5 library code.
    - Easier Testing: These small functions are simple to unit-test.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
import h5py

# Create a logger for this module
log = logging.getLogger(__name__)


def check_attribute(
    obj: h5py.File | h5py.Group | h5py.Dataset,
    attr_name: str,
    expected_type: type | tuple[type, ...],
    file_rel_path: str,
) -> bool:
    """
    Verifies that a specific attribute exists on an HDF5 object and
    has the correct Python data type.

    Parameters
    ----------
    obj : h5py.File | h5py.Group | h5py.Dataset
        The HDF5 object (file root, group, or dataset) to check.
    attr_name : str
        The name of the attribute (e.g., "patient_id").
    expected_type : type | tuple[type, ...]
        The expected Python type (e.g., str, int, list).
    file_rel_path : str
        The relative path of the file being validated (for error logging).

    Returns
    -------
    bool
        True if the attribute exists and has the correct type.
        False if it's missing or has the wrong type.
    """
    # 1. Check if the attribute exists at all
    if attr_name not in obj.attrs:
        log.error("[%s] Missing required attribute: '%s'", file_rel_path, attr_name)
        return False

    # 2. Get the actual value and its type
    val = obj.attrs[attr_name]

    # HDF5 often returns strings as bytes (b"example") in Python 3.
    # We should normalize them to strings if we're checking for 'str'.
    if isinstance(val, bytes) and expected_type == str:
        val = val.decode("utf-8")

    # Special handling for lists/sequences (HDF5 returns them as numpy arrays)
    if expected_type in (list, Sequence):
        # We consider numpy arrays or lists as valid for a "list" requirement.
        import numpy as np
        if not isinstance(val, (list, np.ndarray)):
            log.error(
                "[%s] Attribute '%s' has wrong type. Expected list, got %s",
                file_rel_path,
                attr_name,
                type(val).__name__,
            )
            return False
        return True

    # 3. Check the type
    if not isinstance(val, expected_type):
        log.error(
            "[%s] Attribute '%s' has wrong type. Expected %s, got %s",
            file_rel_path,
            attr_name,
            expected_type.__name__ if hasattr(expected_type, "__name__") else str(expected_type),
            type(val).__name__,
        )
        return False

    return True


def check_group_exists(
    parent: h5py.File | h5py.Group,
    group_name: str,
    file_rel_path: str,
    required: bool = True,
) -> bool:
    """
    Checks if a group exists within an HDF5 file or parent group.

    Parameters
    ----------
    parent : h5py.File | h5py.Group
        The parent object to search in.
    group_name : str
        The name of the group (e.g., "demographics").
    file_rel_path : str
        The relative path of the file being validated (for error logging).
    required : bool, optional
        If True, an error is logged if the group is missing.
        If False, it just returns False silently.

    Returns
    -------
    bool
        True if the group exists and is indeed a group.
    """
    if group_name not in parent:
        if required:
            log.error("[%s] Missing required group: '%s/'", file_rel_path, group_name)
        return False

    if not isinstance(parent[group_name], h5py.Group):
        log.error("[%s] '%s' exists but is not a group (it might be a dataset).", file_rel_path, group_name)
        return False

    return True


def check_dataset_exists(
    parent: h5py.Group,
    ds_name: str,
    file_rel_path: str,
    required: bool = True,
) -> bool:
    """
    Checks if a dataset exists within an HDF5 group.

    Parameters
    ----------
    parent : h5py.Group
        The parent group to search in.
    ds_name : str
        The name of the dataset (e.g., "volume").
    file_rel_path : str
        The relative path of the file being validated (for error logging).
    required : bool, optional
        If True, an error is logged if the dataset is missing.

    Returns
    -------
    bool
        True if the dataset exists and is indeed a dataset.
    """
    if ds_name not in parent:
        if required:
            log.error("[%s] Missing required dataset: '%s'", file_rel_path, ds_name)
        return False

    if not isinstance(parent[ds_name], h5py.Dataset):
        log.error("[%s] '%s' exists but is not a dataset (it might be a group).", file_rel_path, ds_name)
        return False

    return True
