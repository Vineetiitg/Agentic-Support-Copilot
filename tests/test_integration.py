"""Integration tests for API endpoints."""
import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoints:
    def test_health_returns_ok(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestAuthEndpoints:
    def test_login_with_valid_credentials(self, test_client):
        response = test_client.post("/auth/login", data={"username": "admin", "password": "admin123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["role"] == "admin"

    def test_login_with_invalid_credentials(self, test_client):
        response = test_client.post("/auth/login", data={"username": "admin", "password": "wrong"})
        assert response.status_code == 401

    def test_login_returns_jwt_token(self, test_client):
        response = test_client.post("/auth/login", data={"username": "user", "password": "user123"})
        data = response.json()
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20


class TestDocumentsEndpoint:
    @patch("app.engine.document_registry.load_registry", return_value={})
    def test_documents_returns_list(self, mock_reg, test_client):
        response = test_client.get("/documents")
        assert response.status_code == 200
        assert "documents" in response.json()


class TestChatEndpoint:
    @patch("app.routers.chat.check_cache", new_callable=AsyncMock, return_value={"answer": "Test answer", "sources": [{"source": "test.md", "snippet": "test"}], "confidence": 0.95})
    @patch("app.routers.chat.async_enforce_rate_limit", new_callable=AsyncMock)
    @patch("app.engine.memory.get_session_history", new_callable=AsyncMock, return_value=[])
    @patch("app.engine.memory.get_session_summary", new_callable=AsyncMock, return_value="")
    @patch("app.engine.memory.add_session_message", new_callable=AsyncMock)
    def test_chat_returns_cached_answer(self, mock_add, mock_summary, mock_history, mock_rate, mock_cache, test_client):
        response = test_client.post("/chat", json={"query": "How to reset password?"})
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data

    def test_chat_rejects_empty_query(self, test_client):
        response = test_client.post("/chat", json={"query": ""})
        assert response.status_code in (400, 422)
