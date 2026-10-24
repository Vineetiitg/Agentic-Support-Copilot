import asyncio
from typing import Any
from arq.connections import RedisSettings
from app.core.config import settings
from app.core.logging import logger
from app.engine.ingestion import ingest_documents


async def async_ingest_documents(ctx: dict[str, Any], data_dir: str = "data/docs", force: bool = False) -> dict[str, Any]:
    logger.info(f"[Arq Worker] Starting document ingestion for dir: {data_dir}, force={force}")
    # Run CPU-heavy synchronous chunking & ONNX embedding in a thread pool so we don't block the asyncio event loop
    await asyncio.to_thread(ingest_documents, data_dir=data_dir, force=force)
    logger.info("[Arq Worker] Document ingestion completed successfully.")
    return {"status": "SUCCESS", "message": "Documents ingested successfully.", "data_dir": data_dir}


async def async_run_ragas_eval(ctx: dict[str, Any], dataset_path: str = None) -> dict[str, Any]:
    logger.info(f"[Arq Worker] Starting RAGAS benchmark evaluation (dataset={dataset_path or 'all 55 questions'})...")
    from pathlib import Path
    from app.tests.eval_rag import run_local_evaluation, REPORT_PATH
    kwargs = {"dataset_path": Path(dataset_path)} if dataset_path else {}
    summary = await run_local_evaluation(**kwargs)
    logger.info(f"[Arq Worker] RAGAS evaluation completed. Report saved at: {REPORT_PATH}")
    return {
        "status": "SUCCESS",
        "questions": summary.get("questions", 0),
        "source_hit_rate": summary.get("source_hit_rate", 0.0),
        "report_path": str(REPORT_PATH),
    }


async def async_llm_throttle_call(ctx: dict[str, Any], prompt: str) -> dict[str, Any]:
    """
    Role D: Concurrency Throttled LLM call via Arq queue to prevent OpenRouter HTTP 429 errors.
    """
    logger.info("[Arq Worker] Processing throttled LLM request...")
    from app.core.dependencies import get_llm
    llm = get_llm()
    response = await llm.ainvoke(prompt)
    return {"status": "SUCCESS", "content": response.content}


class WorkerSettings:
    functions = [async_ingest_documents, async_run_ragas_eval, async_llm_throttle_call]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 5  # Role D: Concurrency limit per worker container to smooth traffic spikes
    job_timeout = 1800  # 30 minutes max for heavy evaluation or ingestion jobs
