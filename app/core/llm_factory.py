"""Centralized LLM factory. All modules should import LLM instances from here."""
import httpx
from functools import lru_cache
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.core.logging import logger

_http_client = httpx.AsyncClient(
    http2=True,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    timeout=httpx.Timeout(60.0, connect=10.0),
)

_DEFAULT_HEADERS = {
    "HTTP-Referer": "https://localhost:3000",
    "X-Title": "Support Docs Copilot",
}

def create_llm(
    model: str | None = None,
    temperature: float = 0,
    use_async_client: bool = True,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance with standardized configuration."""
    _model = model or settings.LLM_MODEL
    kwargs = dict(
        model=_model,
        temperature=temperature,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        default_headers=_DEFAULT_HEADERS,
    )
    if use_async_client:
        kwargs["http_async_client"] = _http_client
    logger.info(f"Creating LLM instance: model={_model}, temp={temperature}")
    return ChatOpenAI(**kwargs)

@lru_cache(maxsize=4)
def get_fast_llm() -> ChatOpenAI:
    """Fast model for primary generation."""
    return create_llm(model=settings.LLM_MODEL)

@lru_cache(maxsize=4)
def get_slow_llm() -> ChatOpenAI:
    """Slow reasoning model for retries."""
    return create_llm(model=getattr(settings, "SLOW_LLM_MODEL", settings.LLM_MODEL))
