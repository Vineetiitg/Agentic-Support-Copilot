import asyncio
import json
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.queue import get_redis_client
from app.engine.indexer import dense_embeddings

logger = logging.getLogger(__name__)

_cache_verifier = None


def get_cache_verifier(model_name: Optional[str] = None):
    """Singleton getter for Tier B Cross-Encoder verifier."""
    global _cache_verifier
    if _cache_verifier is None:
        if not getattr(settings, "CACHE_CROSS_ENCODER_ENABLED", True):
            return None
        model = model_name or getattr(settings, "CACHE_CROSS_ENCODER_MODEL", "BAAI/bge-reranker-base")
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Initializing Tier B Cross-Encoder cache verifier: {model}")
            _cache_verifier = CrossEncoder(model)
        except Exception as e:
            logger.warning(f"Failed to load Tier B Cross-Encoder verifier ({e})")
            return None
    return _cache_verifier


def verify_cache_match_sync(query: str, cached_query: str, threshold: float = 0.75) -> Tuple[bool, float]:
    """
    Tier B: Cross-Encoder full cross-attention verification.
    Computes bidirectional cross-attention:
        CrossAttention([CLS] o Q_new o [SEP] o Q_cached) and
        CrossAttention([CLS] o Q_cached o [SEP] o Q_new)
    Takes min(fwd, bwd) to eliminate asymmetric semantic bleed (e.g. MP4 vs general formats).
    """
    q1 = re.sub(r"[^\w\s]", "", query).strip().lower()
    q2 = re.sub(r"[^\w\s]", "", cached_query).strip().lower()
    if q1 == q2:
        return True, 1.0

    verifier = get_cache_verifier()
    if verifier is None:
        # Fallback if neural cross-encoder fails to initialize
        return True, 1.0

    try:
        scores = verifier.predict([(query, cached_query), (cached_query, query)])
        fwd_score = float(scores[0])
        bwd_score = float(scores[1])
        min_score = min(fwd_score, bwd_score)
        is_match = min_score >= threshold
        return is_match, min_score
    except Exception as e:
        logger.warning(f"Tier B Cross-Encoder prediction failed ({e}), falling back to cache miss")
        return False, 0.0


async def verify_cache_match(query: str, cached_query: str, threshold: float = 0.75) -> Tuple[bool, float]:
    """Async wrapper to offload CPU-bound cross-encoder inference from the FastAPI event loop."""
    return await asyncio.to_thread(verify_cache_match_sync, query, cached_query, threshold)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


async def _scan_cache_keys(redis, pattern="semantic_cache:*", count=100):
    """Use SCAN cursor instead of KEYS to avoid blocking Redis."""
    keys = []
    cursor = 0
    while True:
        cursor, batch = await redis.scan(cursor=cursor, match=pattern, count=50)
        keys.extend(batch)
        if cursor == 0 or len(keys) >= count:
            break
    return keys[:count]


async def get_cached_answer(query: str, similarity_threshold: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Dual-Tier Semantic Cache Retrieval:
    1. Vector Similarity: Scans Redis candidates with cosine similarity >= similarity_threshold.
    2. Tier B (Cross-Encoder Verifier): Evaluates cross-attention between incoming query and
       cached query to reject semantic bleed (directional contradictions, format mismatches, etc.).
    """
    try:
        redis = await get_redis_client()
        keys = await _scan_cache_keys(redis)
        if not keys:
            return None

        sim_threshold = similarity_threshold if similarity_threshold is not None else getattr(settings, "CACHE_SIMILARITY_THRESHOLD", 0.88)
        ce_threshold = getattr(settings, "CACHE_CROSS_ENCODER_THRESHOLD", 0.75)
        ce_enabled = getattr(settings, "CACHE_CROSS_ENCODER_ENABLED", True)

        embedder = dense_embeddings()
        query_vec = embedder.embed_query(query)

        # 1. Gather vector candidates
        candidates = []
        keys_to_check = keys[:100]
        if keys_to_check:
            raw_values = await redis.mget(*keys_to_check)
            for raw in raw_values:
                if not raw:
                    continue
                data = json.loads(raw)
                cached_vec = data.get("embedding")
                if not cached_vec:
                    continue

                sim = cosine_similarity(query_vec, cached_vec)
                if sim >= sim_threshold:
                    candidates.append((sim, data))

        if not candidates:
            logger.info(f"Semantic cache MISS (no candidates above vector threshold {sim_threshold}) for query: '{query}'")
            return None

        # Sort candidates by vector similarity descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # 2. Tier B: Cross-Encoder Semantic Precision Verification
        for sim, data in candidates:
            cached_query = data.get("query", "")
            if not cached_query:
                continue

            if ce_enabled:
                is_valid, ce_score = await verify_cache_match(query, cached_query, threshold=ce_threshold)
                if not is_valid:
                    logger.info(
                        f"Semantic cache Tier B Cross-Encoder REJECTED bleed match: '{query}' <-> '{cached_query}' "
                        f"(sim: {sim:.4f}, CE score: {ce_score:.4f} < {ce_threshold})"
                    )
                    continue

                logger.info(
                    f"Semantic cache Tier B HIT: '{query}' <-> '{cached_query}' "
                    f"(sim: {sim:.4f}, CE score: {ce_score:.4f} >= {ce_threshold})"
                )
            else:
                ce_score = sim
                logger.info(f"Semantic cache HIT (vector only): '{query}' (sim: {sim:.4f} >= {sim_threshold})")

            # Verified cache hit found
            formatted_sources = []
            for s in data.get("sources", []):
                src_dict = dict(s) if isinstance(s, dict) else {"source": str(s)}
                if "snippet" not in src_dict:
                    src_dict["snippet"] = src_dict.get("page_content", src_dict.get("source", data["answer"]))[:250]
                if "source" not in src_dict:
                    src_dict["source"] = src_dict.get("doc_id", "cached_doc")
                formatted_sources.append(src_dict)

            return {
                "answer": data["answer"],
                "sources": formatted_sources,
                "confidence": data.get("confidence", 0.99),
                "cached": True,
                "similarity": sim,
                "cross_encoder_score": ce_score
            }

        logger.info(f"Semantic cache MISS (all {len(candidates)} vector candidates rejected by Tier B Cross-Encoder) for query: '{query}'")
        return None

    except Exception as e:
        logger.warning(f"Semantic cache lookup failed ({e})")
        return None


async def set_cached_answer(query: str, answer: str, sources: List[Any], confidence: float, ttl_seconds: int = 86400) -> None:
    try:
        redis = await get_redis_client()
        embedder = dense_embeddings()
        query_vec = embedder.embed_query(query)

        formatted_sources = []
        for s in sources:
            if isinstance(s, dict):
                src_dict = dict(s)
                if "snippet" not in src_dict:
                    src_dict["snippet"] = src_dict.get("page_content", src_dict.get("source", str(s)))[:250]
                if "source" not in src_dict:
                    src_dict["source"] = src_dict.get("doc_id", "cached_doc")
                formatted_sources.append(src_dict)
            elif hasattr(s, "dict") or hasattr(s, "model_dump"):
                src_dict = s.model_dump() if hasattr(s, "model_dump") else s.dict()
                if "snippet" not in src_dict:
                    src_dict["snippet"] = getattr(s, "page_content", str(s))[:250]
                if "source" not in src_dict:
                    src_dict["source"] = getattr(s, "metadata", {}).get("source", getattr(s, "metadata", {}).get("doc_id", "cached_doc"))
                formatted_sources.append(src_dict)
            elif hasattr(s, "page_content"):
                formatted_sources.append({
                    "source": getattr(s, "metadata", {}).get("source", getattr(s, "metadata", {}).get("doc_id", "cached_doc")),
                    "doc_id": getattr(s, "metadata", {}).get("doc_id", "cached_doc"),
                    "snippet": s.page_content[:250]
                })
            else:
                formatted_sources.append({"source": "cached_doc", "snippet": str(s)[:250]})

        key = f"semantic_cache:{abs(hash(query))}"
        payload = {
            "query": query,
            "embedding": query_vec,
            "answer": answer,
            "sources": formatted_sources,
            "confidence": confidence
        }
        await redis.setex(key, ttl_seconds, json.dumps(payload))
        logger.info(f"Cached semantic answer for query: '{query}'")

        # LRU eviction: keep cache size bounded
        all_keys = await _scan_cache_keys(redis, count=600)
        if len(all_keys) > 500:
            ttls = []
            for k in all_keys:
                ttl = await redis.ttl(k)
                ttls.append((k, ttl))
            ttls.sort(key=lambda x: x[1])
            to_remove = ttls[:len(all_keys) - 500]
            if to_remove:
                await redis.delete(*[k for k, _ in to_remove])
                logger.info(f"LRU eviction: removed {len(to_remove)} oldest cache entries")
    except Exception as e:
        logger.warning(f"Failed to set semantic cache ({e})")
