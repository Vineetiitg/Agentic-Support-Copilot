import logging

from app.core.config import settings
from app.engine.indexer import open_vector_store
from app.engine.query_transform import query_variants

logger = logging.getLogger(__name__)


def get_retriever():
    qdrant = open_vector_store()
    return qdrant.as_retriever(search_kwargs={"k": settings.RETRIEVAL_TOP_K})


async def retrieve_documents(question: str, chat_history: list[dict] = None, return_variants: bool = False):
    qdrant = open_vector_store()
    retriever = get_retriever()
    documents = []
    seen = set()

    try:
        if hasattr(qdrant, "asimilarity_search_with_score"):
            direct_results = await qdrant.asimilarity_search_with_score(question, k=settings.RETRIEVAL_TOP_K)
        else:
            direct_results = [(doc, 0.85) for doc in await retriever.ainvoke(question)]
    except Exception:
        direct_results = [(doc, 0.85) for doc in await retriever.ainvoke(question)]

    for document, score in direct_results:
        key = document.metadata.get("chunk_id") or document.page_content[:120]
        if key not in seen:
            seen.add(key)
            document.metadata["similarity_score"] = float(score)
            documents.append(document)

    top_sim = max([d.metadata.get("similarity_score", 0.0) for d in documents] + [0.0])
    is_multi_topic = any(sep in question.lower() for sep in [" and ", " as well as ", " also ", "? "]) or question.count("?") > 1

    # Only skip query expansion if direct similarity is very high and NOT multi-part
    if top_sim >= 0.88 and not is_multi_topic and documents:
        logger.info(f"Direct retrieval hit very high similarity ({top_sim:.4f} >= 0.88). Skipping query expansion.")
        final_docs = documents[: settings.RETRIEVAL_TOP_K]
        if return_variants:
            return final_docs, [question]
        return final_docs

    variants = await query_variants(question, chat_history)
    for query in variants:
        if query == question:
            continue
        try:
            if hasattr(qdrant, "asimilarity_search_with_score"):
                results = await qdrant.asimilarity_search_with_score(query, k=settings.RETRIEVAL_TOP_K)
            else:
                results = [(doc, 0.85) for doc in await retriever.ainvoke(query)]
        except Exception:
            results = [(doc, 0.85) for doc in await retriever.ainvoke(query)]
            
        for document, score in results:
            key = document.metadata.get("chunk_id") or document.page_content[:120]
            if key in seen:
                continue
            seen.add(key)
            document.metadata["similarity_score"] = float(score)
            documents.append(document)

    logger.info(
        "retrieval completed query_count=%s returned_chunks=%s reranker_enabled=%s",
        len(variants),
        len(documents),
        settings.RERANKER_ENABLED,
    )
    # Retain up to 12 candidates so cross-encoder reranker can select best across all sub-queries
    max_candidates = max(settings.RETRIEVAL_TOP_K * 2, 12)
    final_docs = documents[:max_candidates]
    if return_variants:
        return final_docs, variants
    return final_docs


def get_reranked_retriever():
    return get_retriever()
