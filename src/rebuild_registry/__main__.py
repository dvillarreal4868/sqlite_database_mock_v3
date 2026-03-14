"""
rebuild_registry/__main__.py

PURPOSE:
    This is the entry point that runs when you type:

        python -m rebuild_registry

    Python sees the `-m` flag, finds the `rebuild_registry` package, and
    then looks for this special `__main__.py` file to execute.

    This file's ONLY job is:
      1. Figure out where the project lives on disk.
      2. Derive the paths to `archive/` and `registry/registry.db`.
      3. Call the `rebuild()` function with those paths.

    All the actual logic lives in `core.py` — this file is just the "launch button."

DIRECTORY ASSUMPTIONS:
    This file assumes the project is laid out like:

        your_project/            <-- PROJECT_ROOT
        ├── src/
        │   └── rebuild_registry/
        │       └── __main__.py  <-- THIS FILE (3 levels deep)
        ├── archive/             <-- where .h5 files live
        └── registry/            <-- where registry.db gets created
"""

from __future__ import annotations  # Lets us use modern type hints on older Python

import logging
from pathlib import Path  # pathlib gives us an object-oriented way to work with file paths

# Relative import: the dot means "from this same package" — grabs rebuild() from core.py
from .core import rebuild

# --- Figure out where the project root is ---
#
# __file__          = /your_project/src/rebuild_registry/__main__.py
# .resolve()        = make it an absolute path (no symlinks or ".." weirdness)
# .parent           = /your_project/src/rebuild_registry/   (go up one level)
# .parent           = /your_project/src/                     (go up again)
# .parent           = /your_project/                         (go up once more = project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Now we can point to the two directories we need:
ARCHIVE_DIR = PROJECT_ROOT / "archive"          # e.g. /your_project/archive/
DB_PATH = PROJECT_ROOT / "registry" / "registry.db"  # e.g. /your_project/registry/registry.db

# --- Set up logging ---
# This configures Python's logging system so that our log.info() calls
# throughout the codebase produce nicely formatted output like:
#   14:30:01  INFO      Created fresh database with 6 tables at ...
logging.basicConfig(
    level=logging.INFO,                         # Show INFO and above (not DEBUG)
    format="%(asctime)s  %(levelname)-8s  %(message)s",  # Timestamp + level + message
    datefmt="%H:%M:%S",                         # Just hours:minutes:seconds
)

# --- Run the rebuild ---
# The `if __name__ == "__main__"` guard ensures this only runs when executed directly
# (via `python -m rebuild_registry`), not when imported by another module.
if __name__ == "__main__":
    rebuild(archive_dir=ARCHIVE_DIR, db_path=DB_PATH)
