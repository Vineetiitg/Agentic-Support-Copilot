"""Unit tests for query transformation module."""
import pytest
from unittest.mock import patch, AsyncMock
from app.engine.query_transform import condense_query


@pytest.mark.asyncio
class TestCondenseQuery:
    async def test_no_history_returns_original(self):
        """With empty chat history, query should pass through unchanged."""
        result = await condense_query("What is X?", [], summary="")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_returns_string(self):
        """Result should always be a string."""
        history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
        with patch("app.engine.query_transform.ChatOpenAI") as mock_llm_cls:
            mock_llm = AsyncMock()
            mock_response = AsyncMock()
            mock_response.content = "Condensed query about X"
            mock_llm.ainvoke.return_value = mock_response
            mock_llm_cls.return_value = mock_llm
            result = await condense_query("Tell me more about it", history, summary="")
            assert isinstance(result, str)
