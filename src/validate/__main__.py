"""
validate/__main__.py

PURPOSE:
    This is the CLI entry point for the validation tool.
    It allows users to run:
        python -m validate --all
        python -m validate --patient P001

    It handles:
      - Argument parsing (using argparse).
      - Project root and archive directory derivation.
      - Global logging configuration.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Relative imports to grab the orchestration logic
from .core import validate_file, validate_all

# Derive the project root based on this file's position (src/validate/__main__.py)
#   __file__         = .../src/validate/__main__.py
#   .parent          = .../src/validate/
#   .parent.parent   = .../src/
#   .parent.parent.parent = .../  (Project Root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive"

# Configure logging to show timestamp, level, and message.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> int:
    """
    Main entry point for the CLI tool.
    Returns 0 on success (all files valid) or 1 if any validation failed.
    """
    parser = argparse.ArgumentParser(
        description="Validate patient HDF5 files against the project specification."
    )
    
    # Mutually exclusive group: either --all or --patient, but not both.
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Validate all .h5 files in the archive/ directory."
    )
    group.add_argument(
        "--patient",
        type=str,
        help="Validate a single patient file (e.g., P001 or patient_001.h5)."
    )

    args = parser.parse_args()

    # --- Case 1: Validate a single patient file ---
    if args.patient:
        patient_id = args.patient
        # Support both "P001" and "patient_001.h5" as inputs
        if not patient_id.endswith(".h5"):
            # If the user passed P001, we might need to map it to patient_001.h5.
            # Assuming the standard naming: patient_XXX.h5 where XXX is numerical part.
            # Let's try to find it in the archive.
            patient_file = None
            if patient_id.startswith("P") and patient_id[1:].isdigit():
                num = patient_id[1:]
                # Many systems use leading zeros, let's assume patient_001.h5 style
                patient_file = ARCHIVE_DIR / f"patient_{num}.h5"
            else:
                patient_file = ARCHIVE_DIR / f"{patient_id}.h5"
        else:
            patient_file = ARCHIVE_DIR / patient_id

        if not patient_file.exists():
            log.error("Could not find patient file at %s", patient_file)
            return 1

        is_valid = validate_file(patient_file, ARCHIVE_DIR)
        return 0 if is_valid else 1

    # --- Case 2: Validate the whole archive ---
    if args.all:
        results = validate_all(ARCHIVE_DIR)
        
        # If no files were found, we don't necessarily want to return an error,
        # but if files WERE found and any failed, return 1.
        if not results:
            return 0
            
        any_failed = any(status is False for status in results.values())
        return 1 if any_failed else 0

    return 0


if __name__ == "__main__":
    # sys.exit() ensures the shell receives the correct exit code (0 or 1).
    sys.exit(main())
