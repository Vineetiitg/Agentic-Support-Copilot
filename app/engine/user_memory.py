import uuid
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import models
from app.core.config import settings
from app.core.dependencies import get_qdrant_client
from app.engine.indexer import dense_embeddings
from app.core.llm_factory import get_fast_llm
from app.core.logging import logger

COLLECTION_NAME = "user_profiles"

def get_profile_store() -> QdrantVectorStore:
    client = get_qdrant_client()
    exists = any(collection.name == COLLECTION_NAME for collection in client.get_collections().collections)
    if not exists:
        url_or_path_kwarg = {"url": settings.QDRANT_URL} if settings.QDRANT_URL else {"path": settings.QDRANT_LOCATION}
        QdrantVectorStore.from_documents(
            [Document(page_content="User profile initialized.", metadata={"user_id": "init"})],
            embedding=dense_embeddings(),
            collection_name=COLLECTION_NAME,
            **url_or_path_kwarg,
        )
    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=dense_embeddings(),
    )

async def extract_and_save_user_facts(user_id: str, message: str) -> None:
    llm = get_fast_llm()
    prompt = f"""Extract any personal facts the user is sharing about themselves in the message below (e.g., their name, grade, job, OS, preferences, subscription tier).
If there are no personal facts, return 'NONE'.
If there are facts, return them as a concise comma-separated list.
User Message: "{message}"
Extracted Facts:"""
    try:
        response = await llm.ainvoke(prompt)
        facts_text = response.content.strip()
        if facts_text.upper() != 'NONE' and facts_text:
            store = get_profile_store()
            docs = []
            for fact in facts_text.split(','):
                fact = fact.strip()
                if fact:
                    docs.append(Document(page_content=fact, metadata={"user_id": user_id, "fact_id": str(uuid.uuid4())}))
            if docs:
                store.add_documents(docs)
                logger.info(f"Saved {len(docs)} personal facts for user {user_id}: {facts_text}")
    except Exception as e:
        logger.error(f"Failed to extract facts: {e}")

async def retrieve_user_profile(user_id: str, query: str) -> str:
    store = get_profile_store()
    try:
        filter_kwargs = {"filter": models.Filter(must=[models.FieldCondition(key="metadata.user_id", match=models.MatchValue(value=user_id))])}
        results = await store.asimilarity_search(query, k=5, **filter_kwargs)
        if results:
            facts = [doc.page_content for doc in results if doc.page_content != "User profile initialized."]
            if facts:
                return "User Profile Facts: " + ", ".join(facts)
    except Exception as e:
        logger.error(f"Failed to retrieve facts: {e}")
    return ""

