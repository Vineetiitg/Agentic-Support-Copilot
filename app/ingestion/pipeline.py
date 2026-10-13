"""Pipeline entrypoint for document ingestion.
Aliases app.engine.ingestion.
"""
from app.engine.ingestion import (
    ingest_documents,
    list_documents,
    delete_indexed_document,
    reset_index,
    main,
)

__all__ = [
    "ingest_documents",
    "list_documents",
    "delete_indexed_document",
    "reset_index",
    "main",
]

if __name__ == "__main__":
    main()

