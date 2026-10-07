"""Shared test fixtures for the Agentic Support Copilot test suite."""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure auth is disabled for tests
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-real")
os.environ.setdefault("REDIS_URL", "")
os.environ["QDRANT_LOCATION"] = ":memory:"

@pytest.fixture(autouse=True)
def reset_qdrant_client():
    """Reset the shared Qdrant client before and after each test."""
    from app.core.config import settings
    import app.core.dependencies as deps
    import app.engine.user_memory as user_mem
    import app.engine.indexer as indexer
    
    # Force memory mode for tests to prevent locks
    settings.QDRANT_LOCATION = ":memory:"
    
    with deps._client_lock:
        deps._qdrant_client = None
    
    # Reset collection existence flags
    user_mem._collection_exists = False
    indexer._collection_exists = False if hasattr(indexer, '_collection_exists') else None
    
    # Initialize collections for tests
    from langchain_core.documents import Document
    client = deps.get_qdrant_client()
    
    # Initialize support_docs collection if needed
    if not any(c.name == settings.COLLECTION_NAME for c in client.get_collections().collections):
        indexer.index_documents([Document(page_content="Test document", metadata={"doc_id": "test"})])
    
    # Initialize user_profiles collection if needed
    if not any(c.name == "user_profiles" for c in client.get_collections().collections):
        from app.engine.user_memory import get_profile_store
        get_profile_store()
    
    yield
    
    with deps._client_lock:
        deps._qdrant_client = None
    user_mem._collection_exists = False



@pytest.fixture
def test_client():
    """Create a FastAPI TestClient with auth disabled."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Generate admin JWT headers for protected endpoints."""
    from app.auth.security import create_access_token
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers():
    """Generate regular user JWT headers."""
    from app.auth.security import create_access_token
    token = create_access_token(data={"sub": "testuser", "role": "user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_redis():
    """Mock Redis client for tests that don't need real Redis."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.keys.return_value = []
    mock.scan.return_value = (0, [])
    mock.exists.return_value = False
    mock.pipeline.return_value = mock
    mock.execute.return_value = [0, True, 0, True]
    return mock
