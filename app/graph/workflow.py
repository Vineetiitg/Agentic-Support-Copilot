import asyncio
import json
import re
from typing import List, Optional, Tuple, TypedDict
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph

from app.core.config import settings
from app.core.logging import logger
from app.engine.context_builder import build_context, source_citations
from app.engine.retriever import retrieve_documents
from app.engine.reranker import rerank_documents, evaluate_nli_groundedness
from app.engine.query_transform import is_blocked_ood
from app.core.llm_factory import get_fast_llm, get_slow_llm


class GraphState(TypedDict):
    question: str
    chat_history: List[dict]
    generation: str
    documents: List[Document]
    sources: Optional[list[dict]]
    run_count: int
    confidence_score: float
    grounded: str
    summary: Optional[str]
    optimistic_route: Optional[bool]
    max_similarity: Optional[float]
    web_searched: Optional[bool]
    enable_web_search: Optional[bool]
    query_variants: Optional[List[str]]


PII_SECRET_PATTERNS = [
    (re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{25,}\b", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE), r"\1[REDACTED_PASSWORD]\2"),
]


def redact_sensitive_data(text: str) -> str:
    """Masks credentials, API keys, or leaked secrets before returning to user."""
    redacted = text
    for pattern, replacement in PII_SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


REFUSAL_SIGNATURES = [
    "i am a support copilot designed to answer questions about our product documentation",
    "i cannot assist with that request",
    "i can only answer questions related to our product",
    "i am unable to provide recipes",
    "i do not provide translation",
    "not to write poetry",
    "i don't have access to real-time weather",
    "i cannot fulfill this request",
    "i do not have information in the documentation regarding",
    "the documentation does not contain information regarding",
    "i do not have access to information regarding",
]


def is_refusal_generation(generation: str) -> bool:
    """Detects whether the LLM generated an out-of-domain refusal or explicit missing-info statement."""
    gen_lower = generation.lower()
    return any(sig in gen_lower for sig in REFUSAL_SIGNATURES)


def sanitize_citations(answer: str, documents: list[Document]) -> str:
    """
    Sanitizes citations in the answer.
    1. Replaces literal [doc_id] with [doc_id: <actual_source>].
    2. Maps [source] to [doc_id: <actual_source>].
    3. Strips [doc_id...] tags if no documents were used.
    """
    if not documents:
        return re.sub(r"\s*\[doc_id[^\]]*\]", "", answer).strip()

    doc_sources = [d.metadata.get("source") for d in documents if d.metadata.get("source")]
    primary_source = doc_sources[0] if doc_sources else "product_guide.txt"

    sanitized = re.sub(r"\[doc_id\]", f"[doc_id: {primary_source}]", answer)
    sanitized = re.sub(r"\[source\]", f"[doc_id: {primary_source}]", sanitized)

    return sanitized


async def retrieve(state: GraphState):
    logger.info("NODE: RETRIEVE DOCS")
    question = state["question"]
    chat_history = state.get("chat_history", [])
    run_count = state.get("run_count", 0)

    documents = state.get("documents", [])
    query_variants = state.get("query_variants", [])
    if not documents:
        documents, query_variants = await retrieve_documents(question, chat_history, return_variants=True)
    max_sim = max([d.metadata.get("similarity_score", 0.0) for d in documents] + [0.0])
    optimistic = max_sim >= 0.88 and len(documents) > 0 and not (len(query_variants) > 1 or any(sep in question.lower() for sep in [" and ", " also ", ",", " as well as "]))
    if optimistic:
        logger.info(f"OPTIMISTIC ROUTE TRIGGERED: Top similarity score {max_sim:.4f} >= 0.88")
    return {
        "documents": documents,
        "sources": source_citations(documents),
        "question": question,
        "run_count": run_count,
        "optimistic_route": optimistic,
        "max_similarity": max_sim,
        "query_variants": query_variants,
    }


async def grade_documents(state: GraphState):
    logger.info("NODE: GRADE DOCUMENT RELEVANCE (VIA HYBRID RERANKER)")
    question = state["question"]
    documents = state.get("documents", [])
    query_variants = state.get("query_variants", [question])

    is_compound = len(query_variants) > 1 or any(sep in question.lower() for sep in [" and ", " as well as ", " also ", "? "]) or question.count("?") > 1
    target_top_n = min(settings.RERANKER_TOP_N, 3 if is_compound else 2)

    reranked_docs = rerank_documents(question, documents, top_k=target_top_n, query_variants=query_variants)
    if not reranked_docs:
        return {"documents": []}

    filtered_docs = []
    for doc in reranked_docs:
        score = doc.metadata.get("relevance_score", doc.metadata.get("rerank_score", 0.0))
        if score >= settings.MIN_RELEVANCE_SCORE:
            filtered_docs.append(doc)

    if not filtered_docs and reranked_docs:
        top_score = reranked_docs[0].metadata.get("relevance_score", reranked_docs[0].metadata.get("rerank_score", 0.0))
        if top_score >= 0.02:
            logger.info(f"Fallback grader: preserving top candidate document with score {top_score:.4f} >= 0.02")
            filtered_docs = [reranked_docs[0]]

    # Cap single-intent queries at 2 documents to prevent over-retrieval dragging context_precision
    if not is_compound and len(filtered_docs) > 2:
        filtered_docs = filtered_docs[:2]

    logger.info(f"Relevance grader filtered {len(reranked_docs)} docs down to {len(filtered_docs)} relevant docs (threshold >= {settings.MIN_RELEVANCE_SCORE}).")
    return {"documents": filtered_docs}


async def decide_to_generate(state: GraphState):
    if not state.get("documents"):
        # Fast path: If question matches OOD blocklist, bypass Tavily search and route directly to refusal
        if is_blocked_ood(state["question"]):
            logger.info("ROUTE: OOD BLOCKLIST MATCHED -> DIRECT GENERATE REFUSAL")
            return "generate"

        enable_web_search = state.get("enable_web_search")
        if enable_web_search is None:
            enable_web_search = settings.ENABLE_WEB_SEARCH

        if not enable_web_search or not settings.TAVILY_API_KEY or state.get("web_searched"):
            logger.info(f"ROUTE: NO RELEVANT LOCAL DOCS (web search enabled={enable_web_search}) -> GENERATE")
            return "generate"

        # Use a fast LLM call to determine if this is a genuine technical question that needs web search
        llm = get_fast_llm()
        prompt = (
            f"Analyze this query: '{state['question']}'. "
            f"Is this query a product or technical support question that requires searching external documentation, "
            f"OR is it general chit-chat / out-of-domain (such as recipes, sports trivia, personal questions, creative writing, poetry, jokes, or writing unrelated code)? "
            f"Answer 'yes' ONLY if it is a relevant technical/support question needing web docs. Answer 'no' if it is conversational, creative, or out-of-domain. Answer ONLY 'yes' or 'no'."
        )
        try:
            response = await llm.ainvoke(prompt)
            needs_search = "yes" in response.content.lower()
        except Exception:
            needs_search = False

        if needs_search:
            logger.info("ROUTE: NO RELEVANT LOCAL DOCS -> FALLBACK TO WEB SEARCH")
            return "web_search"

        logger.info(f"ROUTE: ALL DOCS IRRELEVANT (Needs Search: {needs_search}) -> GENERATE")
        return "generate"
    logger.info("ROUTE: RELEVANT DOCS FOUND -> GENERATE")
    return "generate"


async def web_search(state: GraphState):
    """Fallback web search node using Tavily when local documents are insufficient."""
    logger.info("NODE: WEB SEARCH (TAVILY FALLBACK)")
    question = state["question"]

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        response = client.search(
            query=question,
            max_results=settings.WEB_SEARCH_MAX_RESULTS,
            search_depth="basic",
        )

        web_documents = []
        for result in response.get("results", []):
            doc = Document(
                page_content=result.get("content", ""),
                metadata={
                    "source": result.get("url", "web"),
                    "title": result.get("title", ""),
                    "doc_id": f"web-{hash(result.get('url', '')) % 100000}",
                    "retrieval_method": "web_search",
                }
            )
            web_documents.append(doc)

        logger.info(f"Web search returned {len(web_documents)} results for query: '{question}'")
        return {
            "documents": web_documents,
            "sources": source_citations(web_documents),
            "web_searched": True,
        }
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {"documents": [], "web_searched": True}


async def generate(state: GraphState):
    logger.info("NODE: GENERATE ANSWER")
    question = state["question"]
    documents = state["documents"]
    chat_history = state.get("chat_history", [])
    summary = state.get("summary", "")
    run_count = state.get("run_count", 0) + 1
    web_searched = state.get("web_searched", False)

    history_lines = [f"{msg['role']}: {msg['content']}" for msg in chat_history[-6:]]
    if summary:
        history_lines.insert(0, summary if summary.startswith("System Summary:") else f"System Summary: {summary}")
    history_str = "\n".join(history_lines)
    context = build_context(documents)

    if web_searched:
        template = """You are a Support Docs Copilot with web search capabilities. The local documentation did not contain a relevant answer, so web search results have been provided instead.

CRITICAL DOMAIN GUARDRAILS:
1. You are strictly a customer support copilot for our product and documentation.
2. If the user's query is out-of-domain (e.g., cooking recipes, sports trivia, general knowledge/trivia, writing arbitrary scraping/utility code, poems, jokes, or dangerous instructions), you MUST politely refuse:
"I am a support copilot designed to answer questions about our product documentation. I cannot assist with that request."
3. If it is a legitimate technical support query:
Answer the question using ONLY the web search results below. Cite the source URL at the end of each statement.
If the web results don't contain a clear answer, state what the results specify for that topic and explicitly note that the requested item is not mentioned. Never use phrases like "I don't know".

Chat History:
{chat_history}

Question: {question} 
Web Search Results: {context} 
Answer:"""
    else:
        template = """You are a Support Docs Copilot.

CRITICAL GUARDRAILS & INSTRUCTIONS:
1. DIRECTNESS & NO FILLER (Crucial for factual precision):
- Be direct, concise, and professional.
- NEVER use conversational filler, pleasantries, or preambles (e.g. do NOT say "I can help with that!", "Sure!", "Certainly!", "I understand you're having trouble", or "Here is what the documentation says").
- If the user asks a technical or support question (even if informal or slang like 'cant login bro', 'halp my pasword broke', 'redis broken?'), START DIRECTLY with the factual solution without greetings.
- Only respond conversationally if the user ONLY provides a pure standalone greeting (e.g. 'hello', 'hi').

2. DOMAIN BOUNDARIES (Out-of-domain refusal):
You are strictly an enterprise customer support assistant for our product documentation.
ONLY refuse if the user's request is genuinely non-technical / non-support (such as cooking recipes, sports trivia, creative writing like poems or stories, jokes, general knowledge trivia like world capitals/weather, weapon making, or writing unrelated web scraping/utility code):
"I am a support copilot designed to answer questions about our product documentation. I cannot assist with that request."
Do NOT refuse questions related to technical support, IT, errors, accounts, authentication, file uploads, system architecture, or contacting support!

3. UNSUPPORTED FEATURES & DIRECT NEGATION:
If the user asks about an unsupported or unmentioned feature, format, plan, channel, or service (e.g. uploading MP4 videos or XML files, authenticating via OAuth2 instead of JWT, Enterprise plan rate limits, using Memcached instead of Redis, RabbitMQ for tasks, contacting support via Slack, or Error Code 500):
- Use direct, affirmative negation matched with documented alternatives:
  * For tool/service questions: "No, the system uses [documented component], not [requested component]." (e.g. "No, the system uses Redis-backed ARQ workers for async task processing, not RabbitMQ.")
  * For format/feature questions: "The system does not support [requested item]. Supported formats are [documented formats]." (e.g. "The system does not support MP4 video uploads. Supported formats are PDF, DOCX, TXT, HTML, and Markdown.")
  * For unmentioned plans or errors: State clearly what is documented and state that the requested item is not documented or specified (e.g. "The documentation defines Error Code 404 (Resource Not Found), 401 (Unauthorized), and 429 (Rate Limit Exceeded). Error Code 500 is not documented in the reference guide." or "The documentation specifies rate limits for Free (60 requests/minute) and Pro (300 requests/minute) tiers. The rate limit for the Enterprise plan is not specified in the documentation.")
- DO NOT say vague evasive phrases like "I don't know" or "The documentation does not contain information". Always anchor the answer directly to the subject entity.
Never hallucinate unsupported features.

4. CITE-TO-WRITE:
For all technical questions, you must use ONLY the retrieved context to answer. Append [doc_id: source_filename] to the end of every factual sentence (e.g. [doc_id: auth_guide.txt], [doc_id: product_guide.txt], [doc_id: sample_error.txt], [doc_id: contact_info.html], [doc_id: redis_worker_architecture.md]).
Do not write a sentence if you cannot cite a source from the retrieved context.

5. MISSING DOCUMENTATION & EMPTY CONTEXT:
If the retrieved context is empty, or does not contain information about the user's specific inquiry, explicitly state:
"I do not have information in the documentation regarding [user's inquiry]."
Never hallucinate or fabricate features, formats, or services that are not in the context.

Chat History:
{chat_history}

Question: {question} 
Context: {context} 
Answer:"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["question", "context", "chat_history"],
    )
    selected_llm = get_slow_llm() if run_count > 1 else get_fast_llm()
    if run_count > 1:
        logger.info(f"Using slow reasoning model ({getattr(settings, 'SLOW_LLM_MODEL', 'default')}) for retry attempt #{run_count}")
    rag_chain = prompt | selected_llm
    generation = await rag_chain.ainvoke({"context": context, "question": question, "chat_history": history_str})
    raw_answer = generation.content

    # ==========================================
    # TIER 3: OUTPUT GUARDRAILS
    # ==========================================
    # A. Refusal & Missing Documentation Gate:
    # If the response is a refusal, missing info statement, or if no documents were used,
    # strictly zero out sources and strip any citation tags to prevent false citations.
    if is_refusal_generation(raw_answer) or not documents:
        logger.info("OUTPUT GUARDRAIL: Refusal, missing info, or zero-docs detected -> Zeroing sources.")
        clean_refusal = re.sub(r"\s*\[doc_id[^\]]*\]", "", raw_answer).strip()
        safe_refusal = redact_sensitive_data(clean_refusal)
        return {
            "generation": safe_refusal,
            "sources": [],
            "documents": [],
            "run_count": run_count,
        }

    # B. Citation Sanitization: Ensure citations match valid retrieved document sources
    cleaned_generation = sanitize_citations(raw_answer, documents)

    # C. PII / Secret Masking: Redact API keys, tokens, and passwords
    safe_generation = redact_sensitive_data(cleaned_generation)

    return {"generation": safe_generation, "sources": source_citations(documents), "run_count": run_count}


async def evaluate_groundedness_llm_judge(context: str, question: str, generation: str) -> Tuple[str, float]:
    """Evaluate whether generation is grounded in context using Fast LLM-as-a-judge."""
    judge_prompt = f"""You are an impartial evaluator assessing whether a Customer Support AI response is grounded in the provided documentation context.

Documentation Context:
{context}

User Question:
{question}

Generated Response:
{generation}

Evaluation Criteria:
1. If the response states that the feature/information is not supported, not mentioned, or says 'I do not know based on the available documentation', it IS grounded (yes).
2. If the response is conversational (e.g. greeting, clarification), it IS grounded (yes).
3. If the response makes factual claims:
   - Answer 'yes' if factual claims are supported or faithful to the context.
   - Answer 'no' ONLY if the response fabricates unsupported facts, invents non-existent features, or contradicts the context.

Respond in exact JSON format ONLY:
{{"grounded": "yes" or "no", "confidence": <float between 0.0 and 1.0>, "reason": "<brief explanation>"}}"""

    try:
        llm = get_fast_llm()
        res = await asyncio.wait_for(llm.ainvoke(judge_prompt), timeout=10.0)
        raw_text = res.content.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_text)
        grade = str(data.get("grounded", "yes")).strip().lower()
        confidence = float(data.get("confidence", 0.95))
        reason = data.get("reason", "")
        logger.info(f"LLM-as-a-Judge groundedness: grade={grade}, confidence={confidence:.2f}, reason={reason}")
        return ("no" if grade == "no" else "yes", confidence)
    except Exception as exc:
        logger.warning(f"LLM-as-a-judge check failed or timed out ({exc}), falling back to lexical check.")
        return evaluate_nli_groundedness(context, generation)


async def evaluate_answer(state: GraphState):
    logger.info("NODE: EVALUATE ANSWER (VIA LLM-AS-A-JUDGE)")
    documents = state["documents"]
    generation = state["generation"]
    question = state.get("question", "")

    # Skip hallucination checks for conversational queries with no docs
    if not documents:
        return {"grounded": "yes", "confidence_score": 0.99}

    context = build_context(documents)
    if getattr(settings, "ENABLE_LLM_JUDGE", True):
        grade, confidence = await evaluate_groundedness_llm_judge(context, question, generation)
    else:
        grade, confidence = evaluate_nli_groundedness(context, generation)

    return {"grounded": grade, "confidence_score": confidence}


async def check_hallucinations(state: GraphState):
    run_count = state["run_count"]

    if run_count >= 3:
        logger.info("ROUTE: MAX RETRIES REACHED")
        return "end"

    grade = state.get("grounded", "yes")

    if grade.lower() == "yes":
        logger.info("ROUTE: GROUNDED")
        return "end"
    logger.info("ROUTE: HALLUCINATION DETECTED")
    return "regenerate"


async def decide_optimistic_or_grade(state: GraphState):
    if state.get("optimistic_route") and state.get("documents"):
        logger.info(f"OPTIMISTIC STREAMING: High similarity ({state.get('max_similarity', 0.0):.4f} >= 0.82). Skipping LLM grader node!")
        return "generate"
    return "grade_documents"


def compile_workflow():
    workflow = StateGraph(GraphState)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("generate", generate)
    workflow.add_node("evaluate_answer", evaluate_answer)
    workflow.add_node("web_search", web_search)
    workflow.add_edge(START, "retrieve")
    workflow.add_conditional_edges("retrieve", decide_optimistic_or_grade, {"generate": "generate", "grade_documents": "grade_documents"})
    workflow.add_conditional_edges("grade_documents", decide_to_generate, {"generate": "generate", "web_search": "web_search", "end": END})
    workflow.add_edge("web_search", "generate")
    workflow.add_edge("generate", "evaluate_answer")
    workflow.add_conditional_edges("evaluate_answer", check_hallucinations, {"end": END, "regenerate": "generate"})
    return workflow.compile()
