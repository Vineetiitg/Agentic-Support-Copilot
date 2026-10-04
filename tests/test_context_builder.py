"""Unit tests for context building and source citation."""
import pytest
from langchain_core.documents import Document
from app.engine.context_builder import build_context, format_sources, source_citations


SAMPLE_DOCS = [
    Document(page_content="Password reset: Go to Settings > Security.",
             metadata={"source": "faq.md", "doc_id": "faq-001", "chunk_id": "c1"}),
    Document(page_content="Contact support at help@example.com.",
             metadata={"source": "contact.md", "doc_id": "contact-001", "chunk_id": "c2"}),
]


class TestBuildContext:
    def test_builds_context_string(self):
        context = build_context(SAMPLE_DOCS)
        assert "Password reset" in context
        assert "Contact support" in context

    def test_empty_docs_returns_empty(self):
        assert build_context([]) == ""

    def test_deduplicates_identical_content(self):
        """Duplicate documents should be deduplicated."""
        dup_docs = [SAMPLE_DOCS[0], SAMPLE_DOCS[0]]
        context = build_context(dup_docs)
        count = context.count("Password reset")
        assert count == 1, f"Expected 1 occurrence, got {count}"


class TestSourceCitations:
    def test_returns_citation_dicts(self):
        citations = source_citations(SAMPLE_DOCS)
        assert len(citations) >= 1
        assert all("source" in c for c in citations)
        assert all("snippet" in c for c in citations)

    def test_empty_docs_returns_empty(self):
        assert source_citations([]) == []
