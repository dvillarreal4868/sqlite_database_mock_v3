"""
rebuild_registry
~~~~~~~~~~~~~~~~
Drop this directory into src/ and run::

    python -m rebuild_registry

    or

    docker compose run --rm -e PYTHONPATH=src app python -m rebuild_registry

to delete and recreate registry/registry.db from the archive/ directory.
"""

from .core import rebuild

__all__ = ["rebuild"]
