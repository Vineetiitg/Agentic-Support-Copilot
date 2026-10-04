from fastapi import APIRouter, Depends
from app.auth.models import UserContext
from app.auth.security import resolve_user
from app.core.errors import CopilotError
from app.core.queue import get_redis_client
from app.engine.memory import (
    add_session_message,
    delete_session,
    get_session_history,
    get_session_summary,
    list_all_sessions,
    list_user_sessions,
)
from app.models.schemas import InterveneRequest

router = APIRouter()

@router.get("/api/v1/sessions")
async def get_user_sessions_endpoint(user: UserContext = Depends(resolve_user)):
    sessions = await list_user_sessions(user.user_id)
    return {"sessions": sessions}

@router.get("/api/v1/sessions/{session_id}/messages")
async def get_session_messages_endpoint(session_id: str, user: UserContext = Depends(resolve_user)):
    messages = await get_session_history(user.user_id, session_id, limit=50)
    return {"session_id": session_id, "messages": messages}

@router.post("/api/v1/sessions/{session_id}/terminate")
async def terminate_session_endpoint(session_id: str, user: UserContext = Depends(resolve_user)):
    redis = await get_redis_client()
    await redis.setex(f"session:{session_id}:terminate", 60, "1")
    return {"status": "terminated", "session_id": session_id}

@router.delete("/api/v1/sessions/{session_id}")
async def delete_session_endpoint(session_id: str, user: UserContext = Depends(resolve_user)):
    success = await delete_session(user.user_id, session_id)
    return {"status": "ok" if success else "error", "session_id": session_id}

@router.get("/api/v1/admin/sessions")
async def admin_list_sessions_endpoint(user: UserContext = Depends(resolve_user)):
    if user.role != "admin":
        raise CopilotError("Admin privileges required", status_code=403)
    sessions = await list_all_sessions(limit=50)
    return {"sessions": sessions}

@router.get("/api/v1/admin/sessions/{user_id}/{session_id}/messages")
async def admin_get_session_messages_endpoint(user_id: str, session_id: str, user: UserContext = Depends(resolve_user)):
    if user.role != "admin":
        raise CopilotError("Admin privileges required", status_code=403)
    messages = await get_session_history(user_id, session_id, limit=50)
    summary = await get_session_summary(user_id, session_id)
    return {"session_id": session_id, "user_id": user_id, "messages": messages, "summary": summary}

@router.post("/api/v1/admin/sessions/{user_id}/{session_id}/message")
async def admin_intervene_message_endpoint(user_id: str, session_id: str, request: InterveneRequest, user: UserContext = Depends(resolve_user)):
    if user.role != "admin":
        raise CopilotError("Admin privileges required", status_code=403)
    await add_session_message(user_id, session_id, request.role, request.message)
    return {"status": "ok", "message": "Intervention message injected."}
