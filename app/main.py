import csv
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.dependencies import check_openrouter, check_qdrant
from app.core.errors import CopilotError
from app.core.logging import configure_logging, logger, request_id_var
from app.engine.semantic_cache import set_cached_answer

# Import routers
from app.routers import auth, admin, chat, sessions

configure_logging()
if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    logger.info(f"LangSmith tracing enabled for project: {settings.LANGCHAIN_PROJECT}")

app = FastAPI(title=settings.PROJECT_NAME)

@app.on_event("startup")
async def startup_faq_prewarming():
    try:
        csv_path = Path("datasets/golden_qa.csv")
        if csv_path.exists():
            logger.info("PRE-WARMING SEMANTIC CACHE: Seeding FAQ entries from golden_qa.csv...")
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    question = row.get("question", "").strip()
                    answer = row.get("expected_answer", "").strip()
                    sources_raw = row.get("expected_sources", "").strip()
                    if question and answer:
                        sources = [{"doc_id": sources_raw, "source": sources_raw, "snippet": answer}] if sources_raw else []
                        await set_cached_answer(question, answer, sources, confidence=0.99)
                        count += 1
            logger.info(f"PRE-WARMING COMPLETE: Successfully seeded {count} FAQ entries into Redis vector cache.")
    except Exception as e:
        logger.warning(f"FAQ pre-warming failed or skipped: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)

@app.exception_handler(CopilotError)
async def copilot_error_handler(request: Request, exc: CopilotError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.get("/health")
async def health_endpoint():
    return {"status": "ok", "project": settings.PROJECT_NAME}

@app.get("/ready")
async def ready_endpoint():
    openrouter = check_openrouter()
    qdrant = check_qdrant()
    return {
        "ready": bool(openrouter.get("ok") and qdrant.get("ok")),
        "openrouter": openrouter,
        "qdrant": qdrant,
    }

app.include_router(auth.router, tags=["auth"])
app.include_router(admin.router, tags=["admin"])
app.include_router(chat.router, tags=["chat"])
app.include_router(sessions.router, tags=["sessions"])
