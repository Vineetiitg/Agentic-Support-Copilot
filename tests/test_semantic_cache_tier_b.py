import pytest
import json
from unittest.mock import AsyncMock, patch
from app.engine.semantic_cache import (
    get_cached_answer,
    set_cached_answer,
    verify_cache_match,
    cosine_similarity,
)
from app.engine.indexer import dense_embeddings

@pytest.fixture
def mock_embedder():
    embedder = dense_embeddings()
    return embedder

@pytest.mark.asyncio
async def test_verify_cache_match_exact():
    is_match, score = await verify_cache_match("how to reset password", "How to reset password?")
    assert is_match is True
    assert score == 1.0

@pytest.mark.asyncio
async def test_verify_cache_match_paraphrase():
    is_match, score = await verify_cache_match(
        "How to change my password?",
        "How do I reset my password?",
        threshold=0.75
    )
    assert is_match is True
    assert score >= 0.75

@pytest.mark.asyncio
async def test_verify_cache_match_semantic_bleed_rejected():
    # Asymmetric intent: general formats vs specific unsupported MP4
    is_match, score = await verify_cache_match(
        "Can I upload MP4 videos?",
        "What file formats are supported for upload?",
        threshold=0.75
    )
    assert is_match is False
    assert score < 0.75

@pytest.mark.asyncio
async def test_verify_cache_match_different_error_rejected():
    is_match, score = await verify_cache_match(
        "What is Error Code 500?",
        "What is Error Code 404?",
        threshold=0.75
    )
    assert is_match is False
    assert score < 0.75

@pytest.mark.asyncio
async def test_get_cached_answer_with_tier_b_hit(mock_embedder):
    cached_query = "How do I reset my password?"
    incoming_query = "How can I change my password?"
    
    # In unit test, simulate candidate passing vector threshold
    # so Tier B Cross-Encoder runs its verification
    incoming_vec = mock_embedder.embed_query(incoming_query)
    payload = {
        "query": cached_query,
        "embedding": incoming_vec,  # High vector similarity candidate
        "answer": "Click forgot password on login screen.",
        "sources": [{"source": "auth_guide.txt", "snippet": "Password reset steps"}],
        "confidence": 0.98
    }
    
    mock_redis = AsyncMock()
    mock_redis.scan = AsyncMock(return_value=(0, [b"semantic_cache:123"]))
    mock_redis.mget = AsyncMock(return_value=[json.dumps(payload)])
    
    with patch("app.engine.semantic_cache.get_redis_client", return_value=mock_redis):
        result = await get_cached_answer(incoming_query, similarity_threshold=0.80)
        assert result is not None
        assert result["cached"] is True
        assert result["answer"] == payload["answer"]
        assert "cross_encoder_score" in result
        assert result["cross_encoder_score"] >= 0.75

@pytest.mark.asyncio
async def test_get_cached_answer_tier_b_rejects_bleed(mock_embedder):
    # Cached question about general file formats
    cached_query = "What file formats are supported for upload?"
    # New question specifically asking about MP4
    incoming_query = "Can I upload MP4 videos?"
    
    # Even if vector similarity was high (e.g. 0.95), Tier B should reject it
    incoming_vec = mock_embedder.embed_query(incoming_query)
    payload = {
        "query": cached_query,
        "embedding": incoming_vec,  # Simulate vector candidate pass
        "answer": "Supported formats are PNG, JPEG, and PDF.",
        "sources": [{"source": "product_guide.txt", "snippet": "Supported formats"}],
        "confidence": 0.95
    }
    
    mock_redis = AsyncMock()
    mock_redis.scan = AsyncMock(return_value=(0, [b"semantic_cache:456"]))
    mock_redis.mget = AsyncMock(return_value=[json.dumps(payload)])
    
    with patch("app.engine.semantic_cache.get_redis_client", return_value=mock_redis):
        result = await get_cached_answer(incoming_query, similarity_threshold=0.80)
        # Tier B Cross-Encoder must REJECT this bleed candidate and return None!
        assert result is None
