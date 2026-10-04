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

from fastapi import Query

@router.get("/api/v1/sessions")
async def get_user_sessions_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user: UserContext = Depends(resolve_user),
):
    all_sessions = await list_user_sessions(user.user_id)
    total = len(all_sessions)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "sessions": all_sessions[start:end],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": end < total,
            "has_previous": page > 1,
        },
    }

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
async def admin_list_sessions_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user: UserContext = Depends(resolve_user)
):
    if user.role != "admin":
        raise CopilotError("Admin privileges required", status_code=403)
    # We might pass a large limit to list_all_sessions since it's just keys, or maybe we assume it returns all if large enough
    all_sessions = await list_all_sessions(limit=10000)
    total = len(all_sessions)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "sessions": all_sessions[start:end],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": end < total,
            "has_previous": page > 1,
        },
    }

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
