"""
validate/rules.py

PURPOSE:
    This module contains the specific validation logic for each section
    of the patient HDF5 file as defined in spec/file_spec.md.

    Each function here corresponds to a group (e.g., demographics, imaging)
    and checks its internal structure and attributes.
"""

from __future__ import annotations

import logging
from typing import Sequence
import h5py
from .helpers import check_attribute, check_group_exists, check_dataset_exists

# Create a logger for this module
log = logging.getLogger(__name__)


def validate_root_attributes(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the top-level attributes on the root group."""
    results = [
        check_attribute(h5, "patient_id", str, file_rel_path),
        check_attribute(h5, "tags", (list, Sequence), file_rel_path),
        check_attribute(h5, "active_irbs", (list, Sequence), file_rel_path),
        check_attribute(h5, "irb_history", (list, Sequence), file_rel_path),
        check_attribute(h5, "created_date", str, file_rel_path),
    ]
    return all(results)


def validate_demographics(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'demographics/' group (Required)."""
    if not check_group_exists(h5, "demographics", file_rel_path, required=True):
        return False
    
    group = h5["demographics"]
    results = [
        check_attribute(group, "age", (int, float), file_rel_path),
        check_attribute(group, "sex", str, file_rel_path),
        check_attribute(group, "diagnosis", str, file_rel_path),
        check_attribute(group, "staging", str, file_rel_path),
    ]
    return all(results)


def validate_changelog(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'changelog/' group (Required)."""
    if not check_group_exists(h5, "changelog", file_rel_path, required=True):
        return False
    
    group = h5["changelog"]
    results = [
        check_attribute(group, "last_modified", str, file_rel_path),
        check_attribute(group, "history", (list, Sequence), file_rel_path),
    ]
    return all(results)


def validate_imaging(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'imaging/' group (Optional)."""
    if not check_group_exists(h5, "imaging", file_rel_path, required=False):
        return True # Optional, so missing is fine
    
    group = h5["imaging"]
    valid = True
    
    # Each subgroup is {modality}_{date}
    for name in group:
        subgroup = group[name]
        if not isinstance(subgroup, h5py.Group):
            log.warning("[%s] imaging/%s is not a group", file_rel_path, name)
            valid = False
            continue
            
        # Check subgroup attributes
        sub_valid = [
            check_attribute(subgroup, "modality", str, file_rel_path),
            check_attribute(subgroup, "scan_date", str, file_rel_path),
            check_attribute(subgroup, "num_slices", int, file_rel_path),
            check_attribute(subgroup, "voxel_spacing_mm", (list, Sequence), file_rel_path),
            check_attribute(subgroup, "body_region", str, file_rel_path),
            check_attribute(subgroup, "source_irb", str, file_rel_path),
        ]
        
        # Check volume dataset
        sub_valid.append(check_dataset_exists(subgroup, "volume", file_rel_path))
        
        if not all(sub_valid):
            valid = False
            
    return valid


def validate_notes(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'Notes/' group (Optional)."""
    if not check_group_exists(h5, "Notes", file_rel_path, required=False):
        return True
    
    group = h5["Notes"]
    valid = True
    
    for name in group:
        subgroup = group[name]
        if not isinstance(subgroup, h5py.Group):
            valid = False
            continue
            
        sub_valid = [
            check_attribute(subgroup, "author", str, file_rel_path),
            check_attribute(subgroup, "date", str, file_rel_path),
            check_attribute(subgroup, "category", str, file_rel_path),
            check_attribute(subgroup, "reviewed", (bool, int), file_rel_path), # HDF5 may store bool as int
            check_dataset_exists(subgroup, "text", file_rel_path),
        ]
        if not all(sub_valid):
            valid = False
            
    return valid


def validate_chart_review(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'chart_review/' group (Optional)."""
    if not check_group_exists(h5, "chart_review", file_rel_path, required=False):
        return True
    
    group = h5["chart_review"]
    valid = True
    
    # Should have 'human' and 'llm' subgroups
    for sub in ["human", "llm"]:
        if check_group_exists(group, sub, file_rel_path, required=False):
            sub_group = group[sub]
            for note_id in sub_group:
                note_group = sub_group[note_id]
                if not isinstance(note_group, h5py.Group):
                    continue
                
                # Common field
                check_attribute(note_group, "location", str, file_rel_path)
                
                if sub == "human":
                    check_attribute(note_group, "reviewer", str, file_rel_path)
                    check_attribute(note_group, "review_date", str, file_rel_path)
                else:
                    check_attribute(note_group, "model", str, file_rel_path)
                    check_attribute(note_group, "run_date", str, file_rel_path)
                    
    return valid

def validate_data(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'data/' group (Optional)."""
    if not check_group_exists(h5, "data", file_rel_path, required=False):
        return True
    return True # Further detailed checks could be added per data type

def validate_genomics(h5: h5py.File, file_rel_path: str) -> bool:
    """Checks the 'genomics/' group (Optional)."""
    if not check_group_exists(h5, "genomics", file_rel_path, required=False):
        return True
    
    group = h5["genomics"]
    valid = True
    for assay in group:
        subgroup = group[assay]
        if not isinstance(subgroup, h5py.Group):
            continue
        sub_valid = [
            check_attribute(subgroup, "sequencing_platform", str, file_rel_path),
            check_attribute(subgroup, "coverage", int, file_rel_path),
            check_attribute(subgroup, "reference_genome", str, file_rel_path),
        ]
        if not all(sub_valid):
            valid = False
    return valid
