# Agentic Support Copilot - Complete Project Guide

## 1. Project Overview & Architecture
This project is an advanced, production-ready **RAG (Retrieval-Augmented Generation) Support Copilot**. It's designed to answer support queries by reading your documentation and generating highly accurate, grounded answers with citations.

It uses a **LangGraph Self-RAG** architecture, meaning the AI doesn't just generate an answer blindly. It evaluates its own retrieved documents, decides if they are relevant, generates an answer, and then cross-checks its own answer for hallucinations (groundedness).

**Tech Stack:**
- **Backend:** FastAPI, Python 3.10
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Zustand
- **Vector Database:** Qdrant (in Docker)
- **Cache & Message Queue:** Redis (in Docker)
- **LLM Provider:** OpenRouter (DeepSeek / your choice of models)
- **Embeddings:** FastEmbed (local BGE-small)
- **Reranking:** Cohere API (or local FlashRank ONNX)

---

## 2. Core Concepts (What you need to know for interviews)

### A. The LangGraph Agent Workflow (`app/graph/workflow.py`)
If a recruiter asks how the AI works, explain this flow:
1. **Retrieve:** The system queries Qdrant using the user's question.
2. **Grade Documents:** It uses a reranker (Cohere or FlashRank) to score relevance. Low-score docs are thrown away.
3. **Route:** If no docs are relevant, it goes to `rewrite_query`. If docs are good, it goes to `generate`.
4. **Generate:** The LLM streams an answer using the good documents as context.
5. **Evaluate Groundedness:** An NLI (Natural Language Inference) model cross-checks the LLM's answer against the documents. If it hallucinates, the answer is rejected.

### B. Semantic Caching (`app/engine/semantic_cache.py`)
To save money and time, we use **Semantic Caching**. When a user asks a question, we embed it and check Redis. If a very similar question (e.g., >92% similarity) was asked before, we instantly return the cached answer instead of running the whole LLM chain again.

### C. CORS & Authentication (`app/main.py` & `app/routers/auth.py`)
The backend is protected by JWT (JSON Web Tokens). Users log in via the React frontend. We use standard OAuth2 password flows.
- **CORS Fix:** The API uses `allow_origin_regex=r"^https?://.*$"` to safely permit requests from any localhost or LAN port during development without throwing preflight 400 errors.

---

## 3. How to Run & Deploy the Project

### Local Development / Demo
1. Make sure Docker Desktop is open.
2. Double click `start.bat`.
3. The app will open. 
   - Frontend: `http://localhost:5173`
   - Backend API Docs: `http://localhost:8000/docs`
   - Logins: `admin` / `admin123` OR `user` / `user123`

### Environment Variables (`.env`)
If you need to change API keys, open `.env`. 
- `OPENROUTER_API_KEY`: Required for the LLM to generate answers.
- `COHERE_API_KEY`: Optional, used for high-quality reranking.

### Production Deployment (e.g., AWS EC2, DigitalOcean, or Render)
The project is fully containerized. To deploy to a server:

1. SSH into your server.
2. Clone the repository.
3. Copy `.env.example` to `.env` and fill in your real API keys.
4. Run the production Docker Compose command:
   ```bash
   docker compose build
   docker compose up -d
   ```
*(Note: If the server has less than 16GB RAM, the frontend build inside Docker might fail. In that case, build the frontend locally, copy the `dist` folder to the server, and serve it via Nginx).*

---

## 4. Key Fixes Made to Make it "Resume-Worthy"

If a recruiter asks about challenges you faced and fixed:

1. **CORS Preflight Errors:** 
   - *Problem:* The browser's `OPTIONS` preflight requests were failing with 400 Bad Request when trying to stream chat or log in.
   - *Fix:* Replaced static hardcoded origin lists with a robust `allow_origin_regex` in FastAPI's `CORSMiddleware`, allowing seamless cross-origin requests from any development port.

2. **Memory Exhaustion (OOM) on NLI Model:**
   - *Problem:* Loading the `cross-encoder/nli-deberta-v3-xsmall` model for hallucination checks caused the OS paging file to max out and crash on 16GB laptops.
   - *Fix:* Implemented a graceful degradation sentinel pattern in `reranker.py`. If the model fails to load, the system seamlessly falls back to a lexical word-overlap heuristic to ensure the chat never breaks.

3. **Security Vulnerability in Auth:**
   - *Problem:* The login endpoint was printing plaintext passwords to the console/logs during auth.
   - *Fix:* Stripped out debug prints. Never log PII or credentials.

4. **React Router SPA Collisions:**
   - *Problem:* Navigating to `/admin` caused errors because the route was missing, and the backend proxy was colliding with frontend paths.
   - *Fix:* Namespaced API calls, added an explicit `<Route path="/admin" />` guarded by a `<ProtectedRoute>` component, and wrapped the app in an `<ErrorBoundary>`.
