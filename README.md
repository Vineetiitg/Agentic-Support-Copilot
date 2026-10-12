---
title: Support Docs Copilot
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
---

# 🚀 Support Docs Copilot ✨

[![Live Demo on HuggingFace](https://img.shields.io/badge/🤗%20Live%20Demo-HuggingFace%20Spaces-blue)](https://huggingface.co/spaces/vineet88/support-docs-copilot)
[![Deployed on AWS](https://img.shields.io/badge/Deployed%20on-AWS%20EC2-orange?logo=amazon-aws)](https://aws.amazon.com)
[![codecov](https://codecov.io/gh/Vineetiitg/Agentic-Support-Copilot/graph/badge.svg)](https://codecov.io/gh/Vineetiitg/Agentic-Support-Copilot)

Prepare to be blown away! 🌪️ **Support Docs Copilot** is a state-of-the-art, production-ready Advanced RAG support agent. It boasts **Lightning-Fast Speculative Retrieval** via similarity-based routing (DeepSeek / Gemini / OpenRouter), **Qdrant Hybrid Search**, **Cohere & FlashRank Reranking**, **Instant Redis Semantic Caching & Memory**, **Robust Arq Background Workers**, and an intelligent **LangGraph Self-RAG Agent** armed with confidence scoring, query rewriting, enterprise-grade guardrails, and RAGAS benchmark evaluation! 🤯💡

## 🎬 Demo & Previews

<div align="center">
  <img src="./image.png" alt="Support Docs Copilot Core Experience" width="80%">
  <p><em>✨ The Core Chat Experience: Lightning-fast real-time streaming with precise source citations! ✨</em></p>
</div>

<details>
<summary><b>👀 View More Screenshots</b></summary>
<br/>
<div align="center">
  <img src="https://via.placeholder.com/800x450.png?text=Admin+Dashboard+(Live+Sessions)" alt="Admin Dashboard" width="80%">
  <p><em>👑 Admin Dashboard: Live Session Observability & Deep Insights.</em></p>
  
  <img src="https://via.placeholder.com/800x450.png?text=RAGAS+Evaluation+Tab" alt="RAGAS Evaluation" width="80%">
  <p><em>📊 RAGAS Evaluation Tab: Rigorous LLM Benchmarking for Peak Performance.</em></p>
  
  <img src="https://via.placeholder.com/800x450.png?text=Dark+Mode+React+UI" alt="Dark Mode UI" width="80%">
  <p><em>🌙 Dark Mode UI: A stunning, clean, and modern React frontend.</em></p>
</div>
</details>

## 🌟 Key Features

- 🧠 **Speculative Retrieval:** Dynamically routes requests across specialized cutting-edge models!
- ⚡ **Semantic Caching:** Sub-second cached responses dropping turnaround time to a blistering ~15ms!
- 🛡️ **JWT Authentication:** Secure, rock-solid role-based access for admins and users.
- 🦸 **Hallucination Fallback:** Self-RAG agent flawlessly detects and retries hallucinated answers!
- 🎯 **Hybrid Reranking:** Dense + Sparse embeddings supercharged by Cohere/FlashRank.
- 🚀 **Async Background Workers:** Heavy ingestion tasks effortlessly offloaded to Redis Arq.
- 🛑 **Guardrails:** Real-time PII redaction and bulletproof prompt injection protection!

---

## 📁 Project Structure

```text
app/
├── routers/          # API route handlers (chat, admin, auth, sessions)
├── services/         # Business logic layer (chat, feedback)
├── engine/           # RAG pipeline (retrieval, reranking, caching, memory)
├── graph/            # LangGraph agentic workflow
├── guardrails/       # Input validation and output safety
├── auth/             # JWT auth with SQLite user store
├── core/             # Config, logging, LLM factory, dependencies
└── observability/    # Prometheus metrics and monitoring
tests/                # Unit, integration, and evaluation tests
frontend/             # React frontend (Vite + Tailwind + Zustand) 🎨
```

## 🧩 Tech Stack

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-Self--RAG-orange?logo=langchain)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red?logo=qdrant)
![Redis](https://img.shields.io/badge/Redis-Session%20%26%20Cache-DC382D?logo=redis)
![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![Guardrails](https://img.shields.io/badge/Guardrails%20AI-Security-green)
![RAGAS](https://img.shields.io/badge/RAGAS-Evaluation-purple)
![Cohere](https://img.shields.io/badge/Cohere-Reranking-6c47ff?logo=cohere)

---

## 🕸️ LangGraph Architecture

![LangGraph Architecture](./langgraph_architecture.png)

---

## 💫 Core Architectural Highlights

1. ⚡ **Speculative Retrieval with Similarity-Based Routing:**
   - Routes requests dynamically across specialized models: fast path (`google/gemini-2.0-flash-lite-preview-02-05`), default reasoning (`deepseek/deepseek-v4-flash`), and complex problem solving (`deepseek/deepseek-r1`) via OpenRouter / AICredits.
2. 🧠 **Redis Pre-Warmed Vector Cache & Session Memory:**
   - Features semantic caching that returns instant answers for common FAQs (**Sub-second cached responses via semantic similarity matching**, dropping turnaround from ~1,850ms to ~15–60ms 🚀).
   - Manages multi-turn conversation memory with coreference resolution for flawless dialogue flow.
3. 🎯 **Cohere & FlashRank Hybrid Reranking:**
   - Combines dense (`BAAI/bge-small-en-v1.5`) and sparse (`Qdrant/bm25`) embeddings with automatic reranking via **Cohere ClientV2** or local CPU-only **FlashRank**.
   - Replaces slow LLM relevance grading for maximum efficiency.
4. 🛤️ **Speculative Dual-Path Retrieval:**
   - Uses `asyncio.gather()` to execute multi-turn query condensation concurrently with raw vector search.
5. 👷 **Arq Asynchronous Background Workers:**
   - Heavy tasks such as document ingestion, chunking, and vector indexing are offloaded to Redis-backed **Arq workers**, keeping the API non-blocking and highly responsive!
6. 💯 **Answer Confidence Scoring:**
   - The Self-RAG pipeline calculates numerical confidence scores for every generated response, automatically triggering fallback generation or flagging low-confidence answers for human review.

---

## ☁️ Why Scenario B? (Lightweight & Cloud-Ready)

This project is masterfully engineered to remove heavy GPU, PyTorch, and Ollama dependencies:
- **No Multi-GB Downloads:** Leverages API-based LLM inference, eliminating the need to host heavy weights locally.
- **Lightweight CPU Embeddings:** Uses ONNX-based `FastEmbed` for high-speed local vector embeddings without PyTorch bloat!
- **Free Tier Deployment Ready:** Small Docker image footprint (`~60% smaller`), easily deployable on hosting tiers like HuggingFace Spaces, Render, Railway, or Fly.io.

---

<details>
<summary><b>⚡ Quick Start (Click to expand)</b></summary>

## ⚡ Quick Start

1. Clone and install:
   ```bash
   git clone https://github.com/Vineetiitg/Agentic-Support-Copilot.git
   cd Agentic-Support-Copilot
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Setup environment:
   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```
3. Run with Docker Compose:
   ```bash
   docker compose up -d
   ```

</details>

<details>
<summary><b>🚀 Detailed Setup: Docker & Local (Click to expand)</b></summary>

## 🚀 How to Run the Project

You can run this project in two ways: **Option A (Docker Compose - Easiest)** or **Option B (Local Python Environment)**.

### Option A: Running with Docker Compose (Recommended)

1. **Configure Environment Variables:**
   Make sure your `.env` file exists in the root directory and contains your API keys:
   ```env
   PROJECT_NAME="Support Docs Copilot"
   OPENROUTER_API_KEY=your_api_key_here
   OPENROUTER_BASE_URL=https://aicredits.in/v1
   LLM_MODEL=deepseek/deepseek-v4-flash
   FAST_LLM_MODEL=google/gemini-2.0-flash-lite-preview-02-05
   SLOW_LLM_MODEL=deepseek/deepseek-r1
   
   # Vector Database & Retrieval Mode
   QDRANT_LOCATION=./qdrant_data
   COLLECTION_NAME=support_docs
   RETRIEVAL_MODE=dense
   RETRIEVAL_TOP_K=5
   
   # Reranking Config
   COHERE_API_KEY=your_cohere_key_here
   RERANKER_PROVIDER=auto
   RERANKER_MODEL=rerank-english-v3.0
   FLASHRANK_MODEL=ms-marco-TinyBERT-L-2-v2
   RERANKER_ENABLED=true
   RERANKER_TOP_N=3
   
   # Redis & Queue
   REDIS_URL=redis://redis:6379/0
   
   # Observability & Safety
   ENABLE_GUARDRAILS=true
   ENABLE_RAG_EVAL=false
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT="Support Docs Copilot"
   ```

2. **Build and Start the Cluster:**
   ```bash
   docker-compose up --build -d
   ```
   *Or using Make:*
   ```bash
   make build
   make up
   ```

3. **Ingest Sample Documentation:**
   Once the cluster is running, ingest the knowledge base documents into Qdrant:
   ```bash
   docker exec -it $(docker-compose ps -q backend) python -m app.engine.ingestion ingest
   ```
   *Or using Make:*
   ```bash
   make ingest
   ```

4. **Access the Application:**
   - 💬 **React Chat UI (Vite + Tailwind + Zustand):** Open [http://localhost:5173](http://localhost:5173) in your browser.
   - ⚡ **FastAPI Backend & Swagger Docs:** Open [http://localhost:8000/docs](http://localhost:8000/docs).
   - 🗄️ **Qdrant Dashboard:** Open [http://localhost:6333/dashboard](http://localhost:6333/dashboard).

---

### Option B: Running Locally with Python (Without Docker)

1. **Start Qdrant & Redis:**
   Start Qdrant (`docker run -p 6333:6333 qdrant/qdrant`) and Redis (`docker run -p 6379:6379 redis:7-alpine`). Alternatively, configure `QDRANT_LOCATION=./qdrant_data` in `.env` for local disk storage.

2. **Activate Virtual Environment & Install Dependencies:**
   ```bash
   python -m venv venv
   venv\Scripts\activate      # On Windows
   # source venv/bin/activate # On macOS/Linux
   pip install -r requirements.txt
   ```

3. **Ingest Sample Documents:**
   ```bash
   python -m app.engine.ingestion ingest
   ```

4. **Start the Backend API Server:**
   In your first terminal:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Start the React Frontend UI:**
   In a second terminal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

</details>

## 📊 Running Benchmarks & Latency Tests

To test the system across all 5 architectural scenarios (cache hits, reranking speedups, speculative dual-path retrieval, and RAGAS evaluation analysis), execute the deep dry run benchmark suite:

```bash
python benchmark.py
```
*Or inside the Docker container:*
```bash
docker exec -it $(docker-compose ps -q backend) python benchmark.py
```

---

## 🛠️ Makefile Commands

```bash
make build       # Build lightweight Docker images
make up          # Start Qdrant, Redis, Backend API, Arq Worker, and React UI
make ingest      # Ingest documentation into Qdrant inside the container
make test        # Run pytest test suite inside the container
make eval        # Run RAGAS evaluation against golden dataset
make benchmark   # Run the 5-case architectural latency & readiness benchmark
make logs        # View live cluster logs
make down        # Tear down cluster and free ports
```

---

## 🔐 Authentication & Guardrails

- **JWT Authentication:** Protected endpoints require OAuth2 Bearer Tokens. Authenticate via `/auth/login` (default test accounts: `admin / admin123` and `user / user123`).
- **Input Guardrails:** Automatically inspects incoming prompts for injection attacks and enforces rate limiting (30 req/min).
- **Output Guardrails:** Automatically scrubs and redacts Personally Identifiable Information (SSNs, credit card numbers, phone numbers, emails) before delivering answers to the client.

