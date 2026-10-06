import asyncio
import uuid
from app.core.config import settings
from app.core.logging import logger
from app.engine.memory import add_session_message, get_session_history, get_session_summary
from app.engine.query_transform import condense_query
from app.engine.retriever import retrieve_documents
from app.engine.semantic_cache import get_cached_answer, set_cached_answer
from app.guardrails.input import async_enforce_rate_limit, validate_query
from app.guardrails.output import redact_sensitive_data
from app.observability.metrics import RequestMetrics, log_request_metrics, timed_stage

async def resolve_query_speculative(query: str, chat_history: list, summary: str):
    """Run query condensation and speculative retrieval in parallel."""
    speculative_docs = []
    if chat_history:
        condense_task = asyncio.create_task(condense_query(query, chat_history, summary=summary))
        retrieval_task = asyncio.create_task(retrieve_documents(query, chat_history))
        results = await asyncio.gather(condense_task, retrieval_task, return_exceptions=True)
        standalone_query = query if isinstance(results[0], Exception) else results[0]
        raw_docs = [] if isinstance(results[1], Exception) else results[1]
        if raw_docs:
            top_sim = max([d.metadata.get("similarity_score", 0.0) for d in raw_docs] + [0.0])
            if top_sim >= 0.85:
                logger.info(f"SPECULATIVE RETRIEVAL HIT: top similarity {top_sim:.4f}")
                speculative_docs = raw_docs
    else:
        standalone_query = await condense_query(query, chat_history, summary=summary)
    return standalone_query, speculative_docs

async def prepare_chat_context(user_id: str, session_id: str | None, query: str, chat_history: list):
    """Prepare session, history, and run speculative retrieval."""
    from app.engine.user_memory import extract_and_save_user_facts, retrieve_user_profile
    import asyncio
    
    sid = session_id or str(uuid.uuid4())
    if not chat_history:
        chat_history = await get_session_history(user_id, sid, limit=6)
    summary = await get_session_summary(user_id, sid)
    
    # 1. Retrieve user profile and merge with summary
    user_profile = await retrieve_user_profile(user_id, query)
    if user_profile:
        summary = (summary + "\n" + user_profile).strip() if summary else user_profile
        
    # 2. Extract and save new facts in background
    asyncio.create_task(extract_and_save_user_facts(user_id, query))
    
    standalone_query, speculative_docs = await resolve_query_speculative(query, chat_history, summary)
    return sid, chat_history, summary, standalone_query, speculative_docs

async def check_cache(query: str):
    """Check semantic cache for a matching answer."""
    return await get_cached_answer(query)

async def save_exchange(user_id: str, session_id: str, query: str, answer: str, sources: list, confidence: float):
    """Persist both sides of the conversation and cache the answer."""
    if sources:
        await set_cached_answer(query, answer, sources, confidence)
    await add_session_message(user_id, session_id, "user", query)
    await add_session_message(user_id, session_id, "assistant", answer, sources, confidence)
