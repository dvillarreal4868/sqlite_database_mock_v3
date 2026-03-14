"""
rebuild_registry.ingest
~~~~~~~~~~~~~~~~~~~~~~~
Per-domain ingest functions.  Each accepts (cursor, h5_file, source_file)
and returns any state (like patient_id) that downstream ingestors need.
"""

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
