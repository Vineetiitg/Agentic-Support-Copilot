"""Shared test fixtures for the Agentic Support Copilot test suite."""
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure auth is disabled for tests
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-real")
os.environ.setdefault("REDIS_URL", "")


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
