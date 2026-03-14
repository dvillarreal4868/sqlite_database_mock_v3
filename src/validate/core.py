"""
validate/core.py

PURPOSE:
    This is the orchestrator for the validation process. It manages:
    1. Finding the files to validate (single or all).
    2. Opening the HDF5 files safely.
    3. Running the suite of validation rules from rules.py.
    4. Collecting and reporting the final results.

    Like rebuild_registry/core.py, this module is decoupled from the CLI.
"""

from __future__ import annotations

import logging
from pathlib import Path
import h5py

from .rules import (
    validate_root_attributes,
    validate_demographics,
    validate_changelog,
    validate_imaging,
    validate_notes,
    validate_chart_review,
    validate_data,
    validate_genomics,
)

# Create a logger for this module
log = logging.getLogger(__name__)


def validate_file(h5_path: Path, archive_dir: Path) -> bool:
    """
    Validates a single .h5 file against the specification.

    Parameters
    ----------
    h5_path : Path
        Absolute path to the .h5 file.
    archive_dir : Path
        The archive directory (used to compute relative paths for logging).

    Returns
    -------
    bool
        True if the file is valid, False otherwise.
    """
    # Compute a nice relative path for log messages
    try:
        rel_path = str(h5_path.relative_to(archive_dir.parent))
    except ValueError:
        rel_path = h5_path.name

    log.info("Validating %s...", rel_path)

    if not h5_path.exists():
        log.error("File does not exist: %s", h5_path)
        return False

    try:
        # Open in read-only mode
        with h5py.File(str(h5_path), "r") as h5:
            # Run all validation rules
            # We use a list and all() so we can see multiple errors if they exist,
            # though some functions might return early if a group is missing.
            results = [
                validate_root_attributes(h5, rel_path),
                validate_demographics(h5, rel_path),
                validate_changelog(h5, rel_path),
                validate_imaging(h5, rel_path),
                validate_notes(h5, rel_path),
                validate_chart_review(h5, rel_path),
                validate_data(h5, rel_path),
                validate_genomics(h5, rel_path),
            ]
            
            is_valid = all(results)
            
            if is_valid:
                log.info("PASSED: %s", rel_path)
            else:
                log.error("FAILED: %s contains specification errors.", rel_path)
            
            return is_valid

    except Exception:
        log.exception("CRITICAL ERROR: Could not open or read %s", rel_path)
        return False


def validate_all(archive_dir: Path) -> dict[str, bool]:
    """
    Validates all .h5 files in the archive directory.

    Parameters
    ----------
    archive_dir : Path
        Path to the archive directory containing patient files.

    Returns
    -------
    dict[str, bool]
        A mapping of filename to validation status (True/False).
    """
    archive_dir = Path(archive_dir)
    h5_files = sorted(archive_dir.rglob("*.h5"))
    
    if not h5_files:
        log.warning("No .h5 files found in %s", archive_dir)
        return {}

    log.info("Starting validation of %d file(s) in %s", len(h5_files), archive_dir)
    
    results = {}
    passed_count = 0
    
    for h5_path in h5_files:
        status = validate_file(h5_path, archive_dir)
        results[h5_path.name] = status
        if status:
            passed_count += 1
            
    log.info("--- Validation Summary ---")
    log.info("Total files:  %d", len(h5_files))
    log.info("Passed:       %d", passed_count)
    log.info("Failed:       %d", len(h5_files) - passed_count)
    
    return results
