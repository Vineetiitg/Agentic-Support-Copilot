import threading
from typing import Any

import httpx
from qdrant_client import QdrantClient

from app.core.config import settings

_qdrant_client: QdrantClient | None = None
_client_lock = threading.Lock()


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    with _client_lock:
        if _qdrant_client is None:
            if settings.QDRANT_URL:
                _qdrant_client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY or None,
                )
            else:
                _qdrant_client = QdrantClient(path=settings.QDRANT_LOCATION)
        return _qdrant_client


async def check_openrouter() -> dict[str, Any]:
    try:
        headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
        url = (
            f"{settings.OPENROUTER_BASE_URL.rstrip('/v1').rstrip('/')}/api/v1/auth/key"
            if "openrouter.ai" in settings.OPENROUTER_BASE_URL
            else f"{settings.OPENROUTER_BASE_URL}/models"
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
        return {"ok": response.status_code == 200, "status_code": response.status_code}
    except Exception as exc:
        return {"ok": bool(settings.OPENROUTER_API_KEY), "error": str(exc)}


async def check_qdrant() -> dict[str, Any]:
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        return {
            "ok": settings.COLLECTION_NAME in names,
            "collection": settings.COLLECTION_NAME,
            "available_collections": names,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def get_llm(model: str | None = None, temperature: float = 0) -> Any:
    from app.core.llm_factory import create_llm
    return create_llm(model=model, temperature=temperature, use_async_client=False)
