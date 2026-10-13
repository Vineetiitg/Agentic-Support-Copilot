"""Document ingestion package.
Aliases app.engine.ingestion for compatibility.
"""
from app.engine.ingestion import (
    ingest_documents,
    list_documents,
    delete_indexed_document,
    reset_index,
)

__all__ = [
    "ingest_documents",
    "list_documents",
    "delete_indexed_document",
    "reset_index",
]

