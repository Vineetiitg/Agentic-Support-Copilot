from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile
from app.auth.models import UserContext
from app.auth.security import require_admin, resolve_user
from app.core.config import settings
from app.core.errors import CopilotError
from app.core.logging import logger
from app.engine.document_registry import load_registry
from app.engine.ingestion import delete_indexed_document, ingest_documents, reset_index
from app.tests.eval_rag import run_local_evaluation, REPORT_PATH
from app.models.schemas import IngestionRequest

router = APIRouter()

from fastapi import Query
@router.get("/documents")
async def documents_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user: UserContext = Depends(resolve_user)
):
    all_docs = list(load_registry().values())
    total = len(all_docs)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "documents": all_docs[start:end],
        "role": user.role,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
            "has_next": end < total,
            "has_previous": page > 1,
        },
    }

@router.post("/admin/ingest")
async def admin_ingest_endpoint(request: IngestionRequest, user: UserContext = Depends(resolve_user)):
    require_admin(user)
    try:
        from app.core.queue import get_arq_pool
        pool = await get_arq_pool()
        job = await pool.enqueue_job("async_ingest_documents", data_dir=request.data_dir, force=request.force)
        return {"status": "ok", "message": "Ingestion task queued.", "job_id": job.job_id}
    except Exception as e:
        logger.warning(f"Arq enqueue failed ({e}), falling back to synchronous ingestion.")
        ingest_documents(data_dir=request.data_dir, force=request.force)
        return {"status": "ok", "message": "Ingestion completed synchronously."}

@router.post("/admin/upload")
async def admin_upload_endpoint(files: list[UploadFile] = File(...), user: UserContext = Depends(resolve_user)):
    require_admin(user)
    target_dir = Path(settings.DATA_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    for uploaded_file in files:
        filename = Path(uploaded_file.filename or "uploaded.txt").name
        target_path = target_dir / filename
        target_path.write_bytes(await uploaded_file.read())
        saved_files.append(filename)
    return {"status": "ok", "saved_files": saved_files, "data_dir": str(target_dir)}

@router.delete("/admin/documents/{doc_id}")
async def admin_delete_document_endpoint(doc_id: str, user: UserContext = Depends(resolve_user)):
    require_admin(user)
    delete_indexed_document(doc_id)
    return {"status": "ok", "doc_id": doc_id}

@router.post("/admin/reset")
async def admin_reset_endpoint(user: UserContext = Depends(resolve_user)):
    require_admin(user)
    reset_index()
    return {"status": "ok", "message": "Index reset."}

@router.get("/admin/eval")
async def get_eval_endpoint(user: UserContext = Depends(resolve_user)):
    if REPORT_PATH.exists():
        return {"status": "ok", "report": REPORT_PATH.read_text(encoding="utf-8")}
    return {"status": "missing", "report": "No evaluation report found yet. Click 'Run Evaluation Now' below to generate one."}

@router.post("/admin/eval")
async def post_eval_endpoint(user: UserContext = Depends(resolve_user)):
    require_admin(user)
    try:
        from app.core.queue import get_arq_pool
        pool = await get_arq_pool()
        job = await pool.enqueue_job("async_run_ragas_eval")
        return {"status": "ok", "message": "RAGAS evaluation task queued.", "job_id": job.job_id}
    except Exception as e:
        logger.warning(f"Arq enqueue failed ({e}), falling back to synchronous evaluation.")
        summary = await run_local_evaluation()
        report_content = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else "Report generated."
        return {"status": "ok", "summary": summary, "report": report_content}

@router.get("/tasks/status/{job_id}")
async def get_task_status_endpoint(job_id: str, user: UserContext = Depends(resolve_user)):
    try:
        from app.core.queue import get_arq_pool
        from arq.jobs import Job
        pool = await get_arq_pool()
        job = Job(job_id, redis=pool)
        status = await job.status()
        info = await job.info() if status else None
        return {
            "job_id": job_id,
            "status": status.value if status else "unknown",
            "result": getattr(info, "result", None) if info else None
        }
    except Exception as e:
        return {"job_id": job_id, "status": "error", "error": str(e)}

@router.get("/admin/feedback")
async def admin_feedback_analytics(user: UserContext = Depends(resolve_user)):
    require_admin(user)
    from app.services.feedback_service import get_feedback_analytics
    analytics = await get_feedback_analytics()
    return {"status": "ok", **analytics}
