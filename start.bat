@echo off
echo Starting Qdrant and Redis in Docker...
docker compose up -d qdrant redis

echo Starting FastAPI Backend (Port 8000)...
set QDRANT_URL=http://localhost:6333
set REDIS_URL=redis://localhost:6379/0
start "FastAPI Backend" cmd /k "call .\.venv\Scripts\activate.bat && uvicorn app.main:app --port 8000"

echo Starting React Frontend (Port 5173)...
start "React Frontend" cmd /k "cd frontend && npm run dev -- --host"

echo All services started! 
echo React UI is at http://localhost:5173
pause

