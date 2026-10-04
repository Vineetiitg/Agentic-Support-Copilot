"""Feedback persistence and analytics service."""
import json
import time
import logging
from typing import Any
from app.core.queue import get_redis_client

logger = logging.getLogger(__name__)

FEEDBACK_KEY_PREFIX = "feedback:"
FEEDBACK_INDEX_KEY = "feedback:index"


async def store_feedback(
    user_id: str,
    query: str,
    answer: str,
    is_positive: bool,
    comments: str | None = None,
) -> str:
    """Store user feedback in Redis with timestamp."""
    redis = await get_redis_client()
    feedback_id = f"{user_id}:{int(time.time() * 1000)}"
    payload = {
        "feedback_id": feedback_id,
        "user_id": user_id,
        "query": query,
        "answer": answer[:500],
        "is_positive": is_positive,
        "comments": comments or "",
        "timestamp": time.time(),
    }
    await redis.setex(
        f"{FEEDBACK_KEY_PREFIX}{feedback_id}",
        86400 * 30,  # 30-day TTL
        json.dumps(payload),
    )
    # Track in sorted set for ordered retrieval
    await redis.zadd(FEEDBACK_INDEX_KEY, {feedback_id: time.time()})
    logger.info(f"Feedback stored: {feedback_id} (positive={is_positive})")
    return feedback_id


async def get_feedback_analytics() -> dict[str, Any]:
    """Compute feedback analytics summary."""
    redis = await get_redis_client()
    all_ids = await redis.zrevrange(FEEDBACK_INDEX_KEY, 0, 499)
    
    total = 0
    positive = 0
    negative = 0
    recent_comments = []
    
    for fid in all_ids:
        raw = await redis.get(f"{FEEDBACK_KEY_PREFIX}{fid}")
        if not raw:
            continue
        fb = json.loads(raw)
        total += 1
        if fb.get("is_positive"):
            positive += 1
        else:
            negative += 1
        if fb.get("comments") and len(recent_comments) < 10:
            recent_comments.append({
                "query": fb["query"][:100],
                "is_positive": fb["is_positive"],
                "comments": fb["comments"][:200],
            })
    
    return {
        "total_feedback": total,
        "positive": positive,
        "negative": negative,
        "satisfaction_rate": round(positive / total * 100, 1) if total > 0 else 0.0,
        "recent_comments": recent_comments,
    }
