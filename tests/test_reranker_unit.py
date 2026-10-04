"""Unit tests for the reranker module."""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from app.engine.reranker import rerank_documents, evaluate_nli_groundedness


SAMPLE_DOCS = [
    Document(page_content="Reset password in Settings.", metadata={"source": "faq.md"}),
    Document(page_content="The weather is sunny today.", metadata={"source": "weather.md"}),
    Document(page_content="Contact support at help@co.com.", metadata={"source": "contact.md"}),
]


class TestReranker:
    def test_returns_empty_for_no_docs(self):
        result = rerank_documents("test query", [], top_k=3)
        assert result == []

    def test_single_doc_returns_unchanged(self):
        single = [SAMPLE_DOCS[0]]
        result = rerank_documents("password reset", single, top_k=3)
        assert len(result) == 1
        assert result[0].page_content == single[0].page_content

    def test_top_k_limits_results(self):
        """Should return at most top_k documents."""
        with patch("app.engine.reranker.get_flashrank_client") as mock_fr:
            mock_client = MagicMock()
            mock_client.rerank.return_value = [
                {"id": "0", "score": 0.9},
                {"id": "2", "score": 0.7},
            ]
            mock_fr.return_value = mock_client
            result = rerank_documents("password", SAMPLE_DOCS, top_k=2)
            assert len(result) <= 2


class TestNLIGroundedness:
    def test_fallback_when_model_unavailable(self):
        """When NLI model can't load, should return safe defaults."""
        with patch("app.engine.reranker.get_nli_model", return_value=None):
            grade, confidence = evaluate_nli_groundedness(
                "The sky is blue.", "The sky is blue according to science."
            )
            assert grade == "yes"
            assert 0.0 <= confidence <= 1.0
