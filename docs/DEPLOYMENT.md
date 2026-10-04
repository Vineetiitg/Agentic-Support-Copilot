# Deployment Guide

## Docker Compose (Recommended)

### Prerequisites
- Docker Engine 24+
- Docker Compose v2+
- Minimum 4GB RAM

### Quick Start

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env
docker compose up --build -d
```

### Verify Deployment

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Service Architecture

| Service   | Port | Purpose                    |
|-----------|------|----------------------------|
| Backend   | 8000 | FastAPI API server         |
| Frontend  | 8501 | Streamlit UI               |
| Redis     | 6379 | Cache, sessions, rate limit|
| Qdrant    | 6333 | Vector database            |
| Worker    | —    | Async task processing      |

## Monitoring

- Health: `GET /health`
- Readiness: `GET /ready`  
- Metrics: `GET /metrics` (Prometheus format)

## Troubleshooting

**Backend won't start:** Check OPENROUTER_API_KEY is set.
**Rate limit errors:** Adjust RATE_LIMIT_RPM in .env (default: 30).
**Redis connection failed:** Verify REDIS_URL and REDIS_PASSWORD.
