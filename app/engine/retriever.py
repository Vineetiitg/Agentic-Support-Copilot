import logging
import re
from typing import List, Tuple

from langchain_core.documents import Document

from app.core.config import settings
from app.engine.indexer import open_vector_store
from app.engine.query_transform import query_variants, is_blocked_ood

logger = logging.getLogger(__name__)

COMPOUND_SPLIT_PATTERN = re.compile(
    r"\s+(?:and\s+what\s+happens\s+if|and\s+what\s+if|and\s+how\s+do\s+i|and\s+how\s+to|as\s+well\s+as|and\s+also)\s+",
    re.IGNORECASE,
)


def decompose_query(question: str) -> list[str]:
    """Decompose compound questions with multiple intents."""
    parts = COMPOUND_SPLIT_PATTERN.split(question)
    cleaned = [p.strip(" ?.,") for p in parts if len(p.strip(" ?.,")) > 3]
    if len(cleaned) > 1:
        return [c if c.endswith("?") else f"{c}?" for c in cleaned]
    return [question]


def get_retriever():
    qdrant = open_vector_store()
    return qdrant.as_retriever(search_kwargs={"k": settings.RETRIEVAL_TOP_K})


def reciprocal_rank_fusion(
    ranked_result_lists: List[List[Tuple[Document, float]]],
    k: int = 60,
) -> List[Document]:
    """
    Combines multiple ranked document lists into a unified list using Reciprocal Rank Fusion (RRF).
    """
    rrf_scores = {}
    doc_store = {}

    for ranked_list in ranked_result_lists:
        for rank, (doc, score) in enumerate(ranked_list, start=1):
            key = doc.metadata.get("chunk_id") or doc.page_content[:120]
            if key not in doc_store:
                doc_store[key] = doc
                doc.metadata["similarity_score"] = float(score)
            else:
                # Keep highest vector similarity score across queries
                doc_store[key].metadata["similarity_score"] = max(
                    doc_store[key].metadata.get("similarity_score", 0.0),
                    float(score),
                )
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k + rank))

    # Sort documents by RRF score
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k_id: rrf_scores[k_id], reverse=True)
    fused_docs = []
    for k_id in sorted_keys:
        doc = doc_store[k_id]
        doc.metadata["rrf_score"] = rrf_scores[k_id]
        fused_docs.append(doc)
    return fused_docs


async def retrieve_documents(question: str, chat_history: list[dict] = None, return_variants: bool = False):
    # 1. Fast OOD blocklist: Return empty immediately for recipes, poems, jokes, scraping
    if is_blocked_ood(question):
        logger.info(f"OOD blocklist matched for query: '{question}'. Skipping retrieval.")
        if return_variants:
            return [], [question]
        return []

    qdrant = open_vector_store()
    retriever = get_retriever()

    # Check if query is compound / multi-part
    sub_queries = decompose_query(question)
    is_compound = len(sub_queries) > 1 or any(sep in question.lower() for sep in [" and ", " as well as ", " also ", "? "]) or question.count("?") > 1

    # First perform search on the primary question
    primary_results = []
    try:
        if hasattr(qdrant, "asimilarity_search_with_score"):
            primary_results = await qdrant.asimilarity_search_with_score(question, k=settings.RETRIEVAL_TOP_K)
        else:
            primary_results = [(doc, 0.85) for doc in await retriever.ainvoke(question)]
    except Exception:
        primary_results = [(doc, 0.85) for doc in await retriever.ainvoke(question)]

    top_sim = max([score for _, score in primary_results] + [0.0])

    # For simple single-topic queries with very high confidence match (>= 0.88), skip expansions
    if top_sim >= 0.88 and not is_compound and primary_results:
        logger.info(f"Direct retrieval hit very high similarity ({top_sim:.4f} >= 0.88). Skipping query expansion.")
        direct_docs = []
        for doc, score in primary_results:
            doc.metadata["similarity_score"] = float(score)
            direct_docs.append(doc)
        final_docs = direct_docs[:3]
        if return_variants:
            return final_docs, [question]
        return final_docs

    # Gather query variants
    variants = await query_variants(question, chat_history)

    # Merge sub-queries from decomposition into variants
    all_queries = [question]
    for sq in sub_queries:
        if sq not in all_queries:
            all_queries.append(sq)
    for v in variants:
        if v not in all_queries:
            all_queries.append(v)

    # Collect ranked lists for each query
    all_ranked_lists = [primary_results]
    for q in all_queries[1:]:
        try:
            if hasattr(qdrant, "asimilarity_search_with_score"):
                res = await qdrant.asimilarity_search_with_score(q, k=settings.RETRIEVAL_TOP_K)
            else:
                res = [(doc, 0.85) for doc in await retriever.ainvoke(q)]
        except Exception:
            res = [(doc, 0.85) for doc in await retriever.ainvoke(q)]
        all_ranked_lists.append(res)

    fused_docs = reciprocal_rank_fusion(all_ranked_lists)

    logger.info(
        "retrieval completed query_count=%s returned_chunks=%s is_compound=%s",
        len(all_queries),
        len(fused_docs),
        is_compound,
    )

    # If compound query, pass up to 10 candidates to reranker; if single-topic, pass 6
    max_candidates = 10 if is_compound else 6
    final_docs = fused_docs[:max_candidates]
    if return_variants:
        return final_docs, all_queries
    return final_docs


def get_reranked_retriever():
    return get_retriever()
