"""Unit tests for document chunking logic."""
import pytest
from langchain_core.documents import Document
from app.engine.chunking import chunk_documents


class TestChunkDocuments:
    def test_chunks_long_document(self):
        """A document longer than chunk_size should be split into multiple chunks."""
        long_text = "This is a test sentence. " * 200  # ~5000 chars
        docs = [Document(page_content=long_text, metadata={"source": "test.txt"})]
        chunks = chunk_documents(docs)
        assert len(chunks) > 1, "Long document should be split into multiple chunks"

    def test_preserves_metadata(self):
        """Source metadata should be preserved in all chunks."""
        docs = [Document(page_content="Short text.", metadata={"source": "test.md", "custom": "value"})]
        chunks = chunk_documents(docs)
        for chunk in chunks:
            assert chunk.metadata["source"] == "test.md"

    def test_assigns_chunk_ids(self):
        """Each chunk should have a unique chunk_id in metadata."""
        text = "Sentence one. " * 100
        docs = [Document(page_content=text, metadata={"source": "test.txt"})]
        chunks = chunk_documents(docs)
        chunk_ids = [c.metadata.get("chunk_id") for c in chunks]
        assert all(cid is not None for cid in chunk_ids), "All chunks must have chunk_id"
        assert len(set(chunk_ids)) == len(chunk_ids), "Chunk IDs must be unique"

    def test_empty_input_returns_empty(self):
        """Empty input should return empty list."""
        assert chunk_documents([]) == []

    def test_short_document_stays_single_chunk(self):
        """A short document should remain as a single chunk."""
        docs = [Document(page_content="Hello world.", metadata={"source": "s.txt"})]
        chunks = chunk_documents(docs)
        assert len(chunks) == 1
