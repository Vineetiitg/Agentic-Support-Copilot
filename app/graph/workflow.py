import json
from typing import List, Optional, TypedDict
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph

from app.core.config import settings
from app.core.logging import logger
from app.engine.context_builder import build_context, source_citations
from app.engine.retriever import retrieve_documents
from app.engine.reranker import rerank_documents, evaluate_nli_groundedness


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


from app.core.llm_factory import get_fast_llm, get_slow_llm


async def retrieve(state: GraphState):
    logger.info("NODE: RETRIEVE DOCS")
    question = state["question"]
    chat_history = state.get("chat_history", [])
    run_count = state.get("run_count", 0)
    
    documents = state.get("documents", [])
    if not documents:
        documents = await retrieve_documents(question, chat_history)
    max_sim = max([d.metadata.get("similarity_score", 0.0) for d in documents] + [0.0])
    optimistic = max_sim >= 0.82
    if optimistic:
        logger.info(f"OPTIMISTIC ROUTE TRIGGERED: Top similarity score {max_sim:.4f} >= 0.82")
    return {
        "documents": documents,
        "sources": source_citations(documents),
        "question": question,
        "run_count": run_count,
        "optimistic_route": optimistic,
        "max_similarity": max_sim,
    }


async def grade_documents(state: GraphState):
    logger.info("NODE: GRADE DOCUMENT RELEVANCE (VIA HYBRID RERANKER)")
    question = state["question"]
    documents = state.get("documents", [])
    
    reranked_docs = rerank_documents(question, documents, top_k=settings.RERANKER_TOP_N)
    if not reranked_docs:
        return {"documents": []}
        
    filtered_docs = []
    for doc in reranked_docs:
        score = doc.metadata.get("relevance_score", doc.metadata.get("rerank_score", 0.0))
        if score >= settings.MIN_RELEVANCE_SCORE:
            filtered_docs.append(doc)
            
    logger.info(f"Relevance grader filtered {len(reranked_docs)} docs down to {len(filtered_docs)} relevant docs (threshold >= {settings.MIN_RELEVANCE_SCORE}).")
    return {"documents": filtered_docs}


async def decide_to_generate(state: GraphState):
    if not state.get("documents"):
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

    # Use a prompt with strict domain guardrails
    if web_searched:
        template = """You are a Support Docs Copilot with web search capabilities. The local documentation did not contain a relevant answer, so web search results have been provided instead.

CRITICAL DOMAIN GUARDRAILS:
1. You are strictly a customer support copilot for our product and documentation.
2. If the user's query is out-of-domain (e.g., cooking recipes, sports trivia, general knowledge/trivia, writing arbitrary scraping/utility code, poems, jokes, or dangerous instructions), you MUST politely refuse:
"I am a support copilot designed to answer questions about our product documentation. I cannot assist with that request."
3. If it is a legitimate technical support query:
Answer the question using ONLY the web search results below. Cite the source URL at the end of each statement.
If the web results don't contain a clear answer, say "I don't know based on the available documentation."

Chat History:
{chat_history}

Question: {question} 
Web Search Results: {context} 
Answer:"""
    else:
        template = """You are a Support Docs Copilot.

CRITICAL GUARDRAILS & INSTRUCTIONS:
1. GREETINGS & PERSONAL INFO:
If the user is just greeting you, making small talk, or making a conversational statement, respond naturally and warmly without citing anything.
If the user asks a personal question about themselves (e.g. their name, class, or preferences), check the System Summary at the top of the Chat History to see if you have that information saved. If you do, answer naturally without citing a doc_id. If you don't, politely tell them you don't know yet.

2. DOMAIN BOUNDARIES (Out-of-domain refusal):
You are strictly an enterprise customer support assistant for our product documentation.
If the user asks questions outside of product support (such as cooking recipes, sports trivia, creative writing like poems or stories, jokes, world facts like capitals, or writing unrelated scraping/utility code), you MUST politely refuse:
"I am a support copilot designed to answer questions about our product documentation. I cannot assist with that request."
Do NOT answer off-topic questions even if you know the answer.

3. UNSUPPORTED FEATURES & MISSING INFORMATION (Adversarial questions):
If the user asks about an unsupported feature, format, plan, or service (e.g., uploading MP4 videos, authenticating via OAuth2 instead of JWT, Enterprise plan rate limits, using Memcached instead of Redis, or uploading XML files) that is NOT present in the retrieved documentation:
Explicitly state that the feature or format is not supported or is not mentioned in the documentation. Do NOT hallucinate features or make up answers.

4. CITE-TO-WRITE:
For all technical questions, you must use ONLY the retrieved context to answer. Append [doc_id] to the end of every factual sentence.
Do not write a sentence if you cannot cite a source from the retrieved context.
If the context does not contain the answer, say "I don't know based on the available documentation."

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
    return {"generation": generation.content, "sources": source_citations(documents), "run_count": run_count}


async def evaluate_answer(state: GraphState):
    logger.info("NODE: EVALUATE ANSWER")
    documents = state["documents"]
    generation = state["generation"]
    
    # Skip hallucination checks for conversational queries with no docs
    if not documents:
        return {"grounded": "yes", "confidence_score": 0.99}
        
    context = build_context(documents)
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
