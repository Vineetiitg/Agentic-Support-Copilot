import hashlib
import math
import re
from typing import Sequence

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import models

from app.core.config import settings
from app.core.dependencies import get_qdrant_client
from app.core.logging import logger


class FallbackEmbeddings:
    """Lightweight deterministic embeddings used when FastEmbed cannot initialize."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b[a-z0-9]+\b", (text or '').lower())

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            bucket = int(hashlib.sha256(token.encode('utf-8')).hexdigest(), 16) % self.dimension
            vector[bucket] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]


class FallbackSparseEmbeddings:
    """No-op sparse embedding fallback used when the native sparse model fails to load."""

    def embed_documents(self, texts: Sequence[str]):
        return [[] for _ in texts]

    def embed_query(self, text: str):
        return []


def retrieval_mode() -> RetrievalMode:
    mode = settings.RETRIEVAL_MODE.lower()
    if mode == "dense":
        return RetrievalMode.DENSE
    if mode == "sparse":
        return RetrievalMode.SPARSE
    return RetrievalMode.HYBRID


_dense_embedder = None
_sparse_embedder = None


def dense_embeddings():
    global _dense_embedder
    if _dense_embedder is None:
        import os
        cache_dir = "/app/data/fastembed_cache" if os.path.exists("/app") else "./data/fastembed_cache"
        os.makedirs(cache_dir, exist_ok=True)
        try:
            _dense_embedder = FastEmbedEmbeddings(model_name=settings.DENSE_EMBEDDING_MODEL, cache_dir=cache_dir)
        except Exception as exc:
            logger.warning(f"FastEmbed dense model initialization failed; using fallback embedding generator: {exc}")
            _dense_embedder = FallbackEmbeddings()
    return _dense_embedder


def sparse_embeddings():
    global _sparse_embedder
    if _sparse_embedder is None:
        import os
        cache_dir = "/app/data/fastembed_cache" if os.path.exists("/app") else "./data/fastembed_cache"
        os.makedirs(cache_dir, exist_ok=True)
        try:
            _sparse_embedder = FastEmbedSparse(model_name=settings.SPARSE_EMBEDDING_MODEL, cache_dir=cache_dir)
        except Exception as exc:
            logger.warning(f"FastEmbed sparse model initialization failed; sparse retrieval disabled: {exc}")
            _sparse_embedder = FallbackSparseEmbeddings()
    return _sparse_embedder


def collection_exists() -> bool:
    client = get_qdrant_client()
    return any(collection.name == settings.COLLECTION_NAME for collection in client.get_collections().collections)


def open_vector_store(validate_collection_config: bool = True) -> QdrantVectorStore:
    if not collection_exists():
        from langchain_core.documents import Document
        index_documents([Document(page_content="Welcome to Support Docs Copilot knowledge base.", metadata={"doc_id": "init"})], force_recreate=True)
    mode = retrieval_mode()
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=settings.COLLECTION_NAME,
        embedding=dense_embeddings(),
        sparse_embedding=sparse_embeddings() if mode != RetrievalMode.DENSE else None,
        retrieval_mode=mode,
        validate_collection_config=validate_collection_config,
    )


def index_documents(documents, force_recreate: bool = False) -> None:
    if force_recreate or not collection_exists():
        mode = retrieval_mode()
        url_or_path_kwarg = {"url": settings.QDRANT_URL} if settings.QDRANT_URL else {"path": settings.QDRANT_LOCATION}
        QdrantVectorStore.from_documents(
            documents,
            embedding=dense_embeddings(),
            sparse_embedding=sparse_embeddings() if mode != RetrievalMode.DENSE else None,
            collection_name=settings.COLLECTION_NAME,
            retrieval_mode=mode,
            force_recreate=force_recreate,
            **url_or_path_kwarg,
        )
        return

    store = open_vector_store()
    store.add_documents(documents)


def reset_collection() -> None:
    client = get_qdrant_client()
    if collection_exists():
        client.delete_collection(settings.COLLECTION_NAME)


def delete_document(doc_id: str) -> None:
    client = get_qdrant_client()
    if not collection_exists():
        return
    client.delete(
        collection_name=settings.COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.doc_id",
                        match=models.MatchValue(value=doc_id),
                    )
                ]
            )
        ),
    )
