from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    chat_history: list[dict] = []
    session_id: str | None = None

class SourceCitation(BaseModel):
    source: str
    page: int | None = None
    chunk_id: str | None = None
    doc_id: str | None = None
    snippet: str

class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: list[SourceCitation] = []
    confidence: float = 0.0
    session_id: str = "default"

class IngestionRequest(BaseModel):
    data_dir: str = "data/docs"
    force: bool = False

class FeedbackRequest(BaseModel):
    query: str
    answer: str
    is_positive: bool = True
    comments: str | None = None

class InterveneRequest(BaseModel):
    message: str
    role: str = "assistant"
