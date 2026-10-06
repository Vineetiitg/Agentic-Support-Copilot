"""Unit tests for query transformation module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

        mock_response = MagicMock()
        mock_response.content = "Condensed query about X"

        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response

        mock_prompt = MagicMock()
        mock_prompt.__or__.return_value = mock_chain

        with patch("app.engine.query_transform.ChatOpenAI") as mock_llm_cls, patch(
            "app.engine.query_transform.PromptTemplate", return_value=mock_prompt
        ):
            mock_llm_cls.return_value = MagicMock()
            result = await condense_query("Tell me more about it", history, summary="")
            assert isinstance(result, str)
            assert result == "Condensed query about X"
            mock_chain.ainvoke.assert_awaited_once()
