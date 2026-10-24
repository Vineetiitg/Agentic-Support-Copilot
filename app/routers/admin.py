import asyncio
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile
from app.auth.models import UserContext
from app.auth.security import require_admin, resolve_user
from app.core.config import settings
from app.core.errors import CopilotError
from app.core.logging import logger
from app.engine.document_registry import load_registry
from app.engine.ingestion import delete_indexed_document, ingest_documents, reset_index
from app.models.schemas import IngestionRequest

REPORT_PATH = Path("reports/eval_report.md")

router = APIRouter()

@router.get("/documents")
async def documents_endpoint(user: UserContext = Depends(resolve_user)):
    return {"documents": list(load_registry().values()), "role": user.role}

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
    report_file = None
    if REPORT_PATH.exists():
        report_file = REPORT_PATH
    else:
        # Search for any recent report in reports/
        reports_dir = Path("reports")
        if reports_dir.exists():
            candidates = sorted(reports_dir.glob("eval_report*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                report_file = candidates[0]

    if report_file and report_file.exists():
        return {"status": "ok", "report": report_file.read_text(encoding="utf-8")}
    return {"status": "missing", "report": "No evaluation report found yet. Click 'Run Evaluation Now' below to generate one."}

@router.post("/admin/eval")
async def post_eval_endpoint(
    payload: dict = None,
    user: UserContext = Depends(resolve_user)
):
    require_admin(user)
    dataset_file = payload.get("dataset") if payload and isinstance(payload, dict) else None
    
    # Try Arq Redis queue first
    try:
        from app.core.queue import get_arq_pool
        pool = await get_arq_pool()
        kwargs = {"dataset_path": dataset_file} if dataset_file else {}
        job = await pool.enqueue_job("async_run_ragas_eval", **kwargs)
        if job and getattr(job, "job_id", None):
            return {"status": "ok", "message": "RAGAS evaluation task queued.", "job_id": job.job_id}
        raise RuntimeError("Arq returned None job")
    except Exception as e:
        logger.warning(f"Arq queue unavailable ({e}), starting evaluation in background task.")
        # Fallback to local background task (non-blocking so HTTP never times out)
        from app.tests.eval_rag import run_local_evaluation
        kwargs = {"dataset_path": Path(dataset_file)} if dataset_file else {}
        bg_job_id = f"local-eval-{uuid.uuid4().hex[:8]}"
        asyncio.create_task(run_local_evaluation(**kwargs))
        return {
            "status": "ok",
            "message": "Evaluation started in background.",
            "job_id": bg_job_id,
        }

@router.get("/tasks/status/{job_id}")
async def get_task_status_endpoint(job_id: str, user: UserContext = Depends(resolve_user)):
    # Local background task check
    if job_id.startswith("local-eval-"):
        if REPORT_PATH.exists() and (time.time() - REPORT_PATH.stat().st_mtime < 1800):
            return {"job_id": job_id, "status": "completed"}
        return {"job_id": job_id, "status": "in_progress"}

    # Arq job check
    try:
        from app.core.queue import get_arq_pool
        from arq.jobs import Job
        pool = await get_arq_pool()
        job = Job(job_id, redis=pool)
        status = await job.status()
        info = await job.info() if status else None

        if not status:
            return {"job_id": job_id, "status": "unknown"}

        if status.value in ("complete", "completed"):
            if info and not info.success:
                return {"job_id": job_id, "status": "failed", "error": str(info.result)}
            return {"job_id": job_id, "status": "completed", "result": getattr(info, "result", None)}
        elif status.value == "not_found":
            if REPORT_PATH.exists():
                return {"job_id": job_id, "status": "completed"}
            return {"job_id": job_id, "status": "failed", "error": "Job not found in queue"}
        else:
            return {"job_id": job_id, "status": status.value}
    except Exception as e:
        logger.warning(f"Failed to check task status for job {job_id}: {e}")
        return {"job_id": job_id, "status": "failed", "error": str(e)}
