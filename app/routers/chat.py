import asyncio
import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.models import UserContext
from app.auth.security import resolve_user
from app.core.config import settings
from app.core.errors import CopilotError
from app.core.logging import logger
from app.core.queue import get_redis_client
from app.engine.memory import add_session_message, get_session_history, get_session_summary
from app.engine.query_transform import condense_query
from app.engine.retriever import retrieve_documents
from app.engine.semantic_cache import get_cached_answer, set_cached_answer
from app.graph.workflow import compile_workflow
from app.guardrails.input import async_enforce_rate_limit, validate_query
from app.guardrails.output import redact_sensitive_data
from app.guardrails.validators import DetectPromptInjection
from app.models.schemas import ChatRequest, ChatResponse, FeedbackRequest
from app.observability.metrics import RequestMetrics, log_request_metrics, timed_stage
from guardrails import Guard

router = APIRouter()
rag_agent = compile_workflow()
input_guard = Guard().use(DetectPromptInjection, on_fail="exception")

async def resolve_query_speculative(query: str, chat_history: list, summary: str):
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
                logger.info(f"SPECULATIVE RETRIEVAL HIT: Raw query '{query}' matched with top similarity {top_sim:.4f} >= 0.85!")
                speculative_docs = raw_docs
    else:
        standalone_query = await condense_query(query, chat_history, summary=summary)
        
    return standalone_query, speculative_docs

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, http_request: Request, user: UserContext = Depends(resolve_user)):
    metrics = RequestMetrics()
    await async_enforce_rate_limit(http_request.client.host if http_request.client else user.user_id)
    validate_query(request.query)
    if settings.ENABLE_GUARDRAILS:
        try:
            input_guard.validate(request.query)
        except Exception as e:
            raise CopilotError(str(getattr(e, "message", e)), status_code=400)

    session_id = request.session_id or str(uuid.uuid4())
    chat_history = request.chat_history
    if not chat_history:
        chat_history = await get_session_history(user.user_id, session_id, limit=6)
    summary = await get_session_summary(user.user_id, session_id)

    standalone_query, speculative_docs = await resolve_query_speculative(request.query, chat_history, summary=summary)

    cached = await get_cached_answer(standalone_query)
    if cached:
        log_request_metrics(metrics, route="/chat (cache hit)", sources=len(cached.get("sources", [])), model="semantic_cache")
        await add_session_message(user.user_id, session_id, "user", request.query)
        await add_session_message(user.user_id, session_id, "assistant", cached["answer"], cached.get("sources", []), cached.get("confidence", 0.99))
        return ChatResponse(query=request.query, answer=cached["answer"], sources=cached.get("sources", []), confidence=cached.get("confidence", 0.99), session_id=session_id)

    initial_state = {"question": standalone_query, "chat_history": chat_history, "summary": summary, "run_count": 0, "documents": speculative_docs}
    try:
        with timed_stage(metrics, "rag_workflow"):
            final_state = await rag_agent.ainvoke(initial_state)
        answer = redact_sensitive_data(final_state.get("generation", "Unable to compile answer."))
        sources = final_state.get("sources", [])
        confidence = final_state.get("confidence_score", 0.0)
        
        if answer and sources:
            await set_cached_answer(standalone_query, answer, sources, confidence)
            await add_session_message(user.user_id, session_id, "user", request.query)
            await add_session_message(user.user_id, session_id, "assistant", answer, sources, confidence)
    except Exception as e:
        raise CopilotError(str(e), status_code=500)

    log_request_metrics(metrics, route="/chat", sources=len(sources), model=settings.LLM_MODEL)
    return ChatResponse(query=request.query, answer=answer, sources=sources, confidence=confidence, session_id=session_id)

@router.post("/chat/feedback")
async def chat_feedback_endpoint(request: FeedbackRequest, user: UserContext = Depends(resolve_user)):
    logger.info("Feedback received", extra={"feedback": request.dict(), "user": user.user_id})
    return {"status": "ok", "message": "Feedback recorded."}

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, http_request: Request, user: UserContext = Depends(resolve_user)):
    await async_enforce_rate_limit(http_request.client.host if http_request.client else user.user_id)
    validate_query(request.query)
    if settings.ENABLE_GUARDRAILS:
        try:
            input_guard.validate(request.query)
        except Exception as e:
            raise CopilotError(str(getattr(e, "message", e)), status_code=400)

    session_id = request.session_id or str(uuid.uuid4())
    chat_history = request.chat_history
    if not chat_history:
        chat_history = await get_session_history(user.user_id, session_id, limit=6)
    summary = await get_session_summary(user.user_id, session_id)

    standalone_query, speculative_docs = await resolve_query_speculative(request.query, chat_history, summary=summary)

    async def token_generator():
        try:
            metrics = RequestMetrics()
            cached = await get_cached_answer(standalone_query)
            if cached:
                log_request_metrics(metrics, route="/chat/stream (cache hit)", sources=len(cached.get("sources", [])), model="semantic_cache")
                await add_session_message(user.user_id, session_id, "user", request.query)
                await add_session_message(user.user_id, session_id, "assistant", cached["answer"], cached.get("sources", []), cached.get("confidence", 0.99))
                yield cached["answer"]
                return

            initial_state = {"question": standalone_query, "chat_history": chat_history, "summary": summary, "run_count": 0, "documents": speculative_docs}
            documents = []
            sources_text = ""
            grounded_result = "yes"
            has_streamed_tokens = False
            streamed_text = ""

            with timed_stage(metrics, "rag_workflow_stream"):
                redis = await get_redis_client()
                async for event in rag_agent.astream_events(initial_state, version="v2"):
                    kind = event["event"]
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    
                    if kind == "on_chat_model_stream" and node_name == "generate":
                        if await redis.exists(f"session:{session_id}:terminate"):
                            await redis.delete(f"session:{session_id}:terminate")
                            yield "\n\n🛑 **[TERMINATED BY USER: Generation was stopped.]**"
                            await add_session_message(user.user_id, session_id, "user", request.query)
                            await add_session_message(user.user_id, session_id, "assistant", streamed_text + "\n\n🛑 [TERMINATED BY USER]", documents or [], 0.0)
                            return
                        chunk = event["data"]["chunk"]
                        if chunk and getattr(chunk, "content", None):
                            has_streamed_tokens = True
                            streamed_text += chunk.content
                            yield redact_sensitive_data(chunk.content)
                            await asyncio.sleep(0.005)
                            
                    elif kind == "on_chain_end":
                        output = event.get("data", {}).get("output")
                        if isinstance(output, dict):
                            if "documents" in output:
                                documents = output["documents"]
                            if "sources" in output:
                                sources_text = output["sources"]
                            if "grounded" in output:
                                grounded_result = output["grounded"]

            if not has_streamed_tokens:
                if not documents:
                    yield "I am sorry, no reliable matching documentation was found."
                else:
                    yield "I am sorry, I could not generate a response based on the available documentation."
                return

            if str(grounded_result).lower() == "no":
                yield "\n\n🚨 **[CANCELLED: This response violated safety guidelines and has been retracted.]**"
                return

            if has_streamed_tokens and documents and str(grounded_result).lower() != "no":
                redacted_text = redact_sensitive_data(streamed_text)
                await set_cached_answer(standalone_query, redacted_text, documents, 0.98)
                await add_session_message(user.user_id, session_id, "user", request.query)
                await add_session_message(user.user_id, session_id, "assistant", redacted_text, documents, 0.98)
                
            log_request_metrics(metrics, route="/chat/stream", sources=len(documents), model=settings.LLM_MODEL)
        except Exception as exc:
            logger.error(f"Streaming error: {exc}", exc_info=True)
            if "429" in str(exc) or "Rate limit" in str(exc) or "free-models-per-day" in str(exc):
                yield "\n\n⚠️ **OpenRouter Daily Limit Reached:** You have exhausted the 50 free requests/day limit on OpenRouter. To continue using free models today without rate limits, add $1 (or 10 credits) to your OpenRouter account, or try again tomorrow when the limit resets."
            else:
                yield f"\n\n⚠️ **Error generating response:** {exc}"

    return StreamingResponse(token_generator(), media_type="text/event-stream")
