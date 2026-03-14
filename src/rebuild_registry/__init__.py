"""
rebuild_registry/__init__.py

PURPOSE:
    This file makes the `rebuild_registry/` directory a Python "package."
    Without this file, Python would not recognize the folder as importable code.

    It also serves as the "front door" to the package.  When someone writes:

        from rebuild_registry import rebuild

    Python looks HERE first.  We import `rebuild` from our `core.py` module
    and re-export it so callers don't need to know about the internal structure.

USAGE:
    Place this entire `rebuild_registry/` folder inside your `src/` directory,
    then run:

        PYTHONPATH=src python -m rebuild_registry

    The `-m` flag tells Python "find a package called rebuild_registry and
    run its __main__.py."
"""

# This line reaches into core.py (same folder) and grabs the `rebuild` function.
# The dot in `.core` means "this directory" — it's a relative import.
from .core import rebuild

# __all__ controls what gets exported when someone does `from rebuild_registry import *`.
# We only want to expose the `rebuild` function as the public API.
__all__ = ["rebuild"]
