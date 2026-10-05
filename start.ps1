$ErrorActionPreference = "Stop"

Write-Host "Starting Qdrant and Redis in Docker..." -ForegroundColor Cyan
docker compose up -d qdrant redis

Write-Host "Starting FastAPI Backend (Port 8000)..." -ForegroundColor Cyan
$env:QDRANT_URL = "http://localhost:6333"
$env:REDIS_URL = "redis://localhost:6379/0"
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\activate; uvicorn app.main:app --port 8000"

Write-Host "Starting React Frontend (Port 5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev -- --host"

Write-Host "All services started! You can close this window." -ForegroundColor Green
Write-Host "Backend API: http://localhost:8000"
Write-Host "React UI: http://localhost:5173"
