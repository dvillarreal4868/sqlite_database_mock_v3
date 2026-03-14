#!/usr/bin/env python3
"""
Entry point for ``python -m rebuild_registry``.

Expects to live at ``<project_root>/src/rebuild_registry/__main__.py``.
Derives archive/ and registry/ paths from the project root.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .core import rebuild

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "archive"
DB_PATH = PROJECT_ROOT / "registry" / "registry.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    rebuild(archive_dir=ARCHIVE_DIR, db_path=DB_PATH)
