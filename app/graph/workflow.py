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


from app.core.llm_factory import get_fast_llm, get_slow_llm


async def retrieve(state: GraphState):
    logger.info("NODE: RETRIEVE DOCS")
    question = state["question"]
    chat_history = state.get("chat_history", [])
    run_count = state.get("run_count", 0)
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
        # Check if web search is enabled and we haven't already web-searched
        if settings.ENABLE_WEB_SEARCH and settings.TAVILY_API_KEY and not state.get("web_searched"):
            logger.info("ROUTE: NO RELEVANT LOCAL DOCS -> FALLBACK TO WEB SEARCH")
            return "web_search"
        logger.info("ROUTE: ALL DOCS IRRELEVANT")
        return "end"
    logger.info("ROUTE: RELEVANT DOCS FOUND")
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

    # Use a slightly different prompt when answering from web search results
    if web_searched:
        template = """You are a Support Docs Copilot with web search capabilities. The local documentation did not contain a relevant answer, so web search results have been provided instead.

Answer the question using the web search results below. Cite the source URL at the end of each statement.
If the web results don't contain a clear answer either, say "I could not find a reliable answer."

Chat History:
{chat_history}

Question: {question} 
Web Search Results: {context} 
Answer:"""
    else:
        template = """You are a Support Docs Copilot. Use only the retrieved context to answer the question concisely.

CRITICAL INSTRUCTION (Cite-to-Write):
You must append [doc_id] to the end of every sentence. Do not write a sentence if you cannot cite a source from the retrieved context. If the context does not contain the answer, say "I don't know".

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
