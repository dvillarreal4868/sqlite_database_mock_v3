"""
rebuild_registry/ingest/__init__.py

PURPOSE:
    This file makes the `ingest/` subdirectory a Python sub-package.
    It also serves as a convenient "re-export" point: instead of writing

        from rebuild_registry.ingest.patients import ingest_patient
        from rebuild_registry.ingest.imaging import ingest_imaging
        # ... etc

    other modules (like core.py) can just write:

        from .ingest import ingest_patient, ingest_imaging, ...

    Each ingest module handles one "domain" of data from the .h5 file:
        patients.py      → reads root attributes + demographics/ group
        imaging.py       → reads imaging/{modality}_{date}/ groups
        data.py          → reads data/{type}/ groups (glucose, PFTs, etc.)
        notes.py         → reads Notes/note_{NNNN}/ groups
        chart_review.py  → reads chart_review/human/ and chart_review/llm/ groups
        genomics.py      → reads genomics/{assay}_{date}/ groups
"""

# Each "from .X import Y" grabs one function from one sibling file.
# The single dot means "this directory."
from .patients import ingest_patient
from .imaging import ingest_imaging
from .data import ingest_data
from .notes import ingest_notes
from .chart_review import ingest_chart_review
from .genomics import ingest_genomics

__all__ = [
    "ingest_patient",
    "ingest_imaging",
    "ingest_data",
    "ingest_notes",
    "ingest_chart_review",
    "ingest_genomics",
]
