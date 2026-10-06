import asyncio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.models import UserContext
from app.auth.security import resolve_user_optional, resolve_user
from app.core.config import settings
from app.core.errors import CopilotError
from app.core.logging import logger
from app.core.queue import get_redis_client
from app.engine.memory import add_session_message
from app.engine.semantic_cache import set_cached_answer
from app.graph.workflow import compile_workflow
from app.guardrails.input import async_enforce_rate_limit, validate_query
from app.guardrails.output import redact_sensitive_data
from app.guardrails.validators import DetectPromptInjection
from app.models.schemas import ChatRequest, ChatResponse, FeedbackRequest
from app.observability.metrics import RequestMetrics, log_request_metrics, timed_stage
from guardrails import Guard
from app.services.chat_service import check_cache, prepare_chat_context, save_exchange

router = APIRouter()
rag_agent = compile_workflow()
input_guard = Guard().use(DetectPromptInjection, on_fail="exception")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, http_request: Request, user: UserContext = Depends(resolve_user_optional)):
    metrics = RequestMetrics()
    await async_enforce_rate_limit(http_request.client.host if http_request.client else user.user_id)
    validate_query(request.query)
    if settings.ENABLE_GUARDRAILS:
        try:
            input_guard.validate(request.query)
        except Exception as e:
            raise CopilotError(str(getattr(e, "message", e)), status_code=400)

    session_id, chat_history, summary, standalone_query, speculative_docs = await prepare_chat_context(
        user.user_id, request.session_id, request.query, request.chat_history
    )

    cached = await check_cache(standalone_query)
    if cached:
        log_request_metrics(metrics, route="/chat (cache hit)", sources=len(cached.get("sources", [])), model="semantic_cache")
        await save_exchange(user.user_id, session_id, request.query, cached["answer"], cached.get("sources", []), cached.get("confidence", 0.99))
        return ChatResponse(query=request.query, answer=cached["answer"], sources=cached.get("sources", []), confidence=cached.get("confidence", 0.99), session_id=session_id)

    initial_state = {"question": standalone_query, "chat_history": chat_history, "summary": summary, "run_count": 0, "documents": speculative_docs}
    try:
        with timed_stage(metrics, "rag_workflow"):
            final_state = await rag_agent.ainvoke(initial_state)
        answer = redact_sensitive_data(final_state.get("generation", "Unable to compile answer."))
        sources = final_state.get("sources", [])
        confidence = final_state.get("confidence_score", 0.0)
        
        if answer and sources:
            await save_exchange(user.user_id, session_id, request.query, answer, sources, confidence)
    except Exception as e:
        raise CopilotError(str(e), status_code=500)

    log_request_metrics(metrics, route="/chat", sources=len(sources), model=settings.LLM_MODEL)
    return ChatResponse(query=request.query, answer=answer, sources=sources, confidence=confidence, session_id=session_id)

@router.post("/chat/feedback")
async def chat_feedback_endpoint(request: FeedbackRequest, user: UserContext = Depends(resolve_user)):
    logger.info("Feedback received", extra={"feedback": request.dict(), "user": user.user_id})
    return {"status": "ok", "message": "Feedback recorded."}

@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, http_request: Request, user: UserContext = Depends(resolve_user_optional)):
    await async_enforce_rate_limit(http_request.client.host if http_request.client else user.user_id)
    validate_query(request.query)
    if settings.ENABLE_GUARDRAILS:
        try:
            input_guard.validate(request.query)
        except Exception as e:
            raise CopilotError(str(getattr(e, "message", e)), status_code=400)

    session_id, chat_history, summary, standalone_query, speculative_docs = await prepare_chat_context(
        user.user_id, request.session_id, request.query, request.chat_history
    )

    async def token_generator():
        try:
            metrics = RequestMetrics()
            cached = await check_cache(standalone_query)
            if cached:
                log_request_metrics(metrics, route="/chat/stream (cache hit)", sources=len(cached.get("sources", [])), model="semantic_cache")
                await save_exchange(user.user_id, session_id, request.query, cached["answer"], cached.get("sources", []), cached.get("confidence", 0.99))
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
                                docs_raw = output["documents"]
                                documents = []
                                for d in docs_raw:
                                    if hasattr(d, "page_content"):
                                        doc_dict = {"source": d.metadata.get("source", "Unknown"), "snippet": d.page_content}
                                        documents.append(doc_dict)
                                    elif isinstance(d, dict):
                                        documents.append(d)
                            if "sources" in output:
                                sources_text = output["sources"]
                            if "grounded" in output:
                                grounded_result = output["grounded"]

            if not has_streamed_tokens:
                if not documents:
                    fallback_msg = "I am sorry, no reliable matching documentation was found."
                else:
                    fallback_msg = "I am sorry, I could not generate a response based on the available documentation."
                yield fallback_msg
                await save_exchange(user.user_id, session_id, request.query, fallback_msg, [], 0.0)
                return

            if str(grounded_result).lower() == "no":
                fallback_msg = "\n\n🚨 **[CANCELLED: This response violated safety guidelines and has been retracted.]**"
                yield fallback_msg
                await save_exchange(user.user_id, session_id, request.query, fallback_msg, documents, 0.0)
                return

            if has_streamed_tokens and str(grounded_result).lower() != "no":
                redacted_text = redact_sensitive_data(streamed_text)
                await save_exchange(user.user_id, session_id, request.query, redacted_text, documents, 0.98)
                
            log_request_metrics(metrics, route="/chat/stream", sources=len(documents), model=settings.LLM_MODEL)
        except Exception as exc:
            logger.error(f"Streaming error: {exc}", exc_info=True)
            if "429" in str(exc) or "Rate limit" in str(exc) or "free-models-per-day" in str(exc):
                yield "\n\n⚠️ **OpenRouter Daily Limit Reached:** You have exhausted the 50 free requests/day limit on OpenRouter. To continue using free models today without rate limits, add $1 (or 10 credits) to your OpenRouter account, or try again tomorrow when the limit resets."
            else:
                yield f"\n\n⚠️ **Error generating response:** {exc}"

    return StreamingResponse(token_generator(), media_type="text/event-stream")
