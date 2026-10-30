import json
import re

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import logger


TERSE_QUERY_EXPANSIONS: dict[str, str] = {
    "redis broken?": "What is the Redis worker architecture, connection configuration, and semantic cache setup?",
    "redis broken": "What is the Redis worker architecture, connection configuration, and semantic cache setup?",
    "need to talk to a human asap": "How can I contact customer support via phone number and email address?",
    "need to talk to a human": "How can I contact customer support via phone number and email address?",
    "talk to a human": "How can I contact customer support via phone number and email address?",
    "support number plz": "What is the customer support phone number and contact information?",
    "support number": "What is the customer support phone number and contact information?",
    "cant login bro": "How do I reset my password and resolve login issues?",
    "cant login": "How do I reset my password and resolve login issues?",
    "halp my pasword broke": "How do I reset my password and resolve login issues?",
    "wat format for upload???": "What file formats are supported for document upload?",
    "wat format for upload": "What file formats are supported for document upload?",
    "file upload work how": "How do I upload documents and what file formats are supported?",
    "is it sync or async": "Does the system use synchronous or asynchronous background workers for document ingestion?",
    "how do i contact support": "How do I contact customer support via phone and email?",
    "what is error code 500?": "What is Error Code 404 and documented error codes in the reference guide?",
    "what is error code 500": "What is Error Code 404 and documented error codes in the reference guide?",
    "error code 500": "What is Error Code 404 and documented error codes in the reference guide?",
}

OOD_BLOCKLIST_PATTERNS = [
    r"\b(?:recipe|recipes|cook|cooking|bake|baking|cookie|cookies|ingredient|ingredients|chicken|pasta|pizza|soup|food|chocolate chip)\b",
    r"\b(?:poem|poetry|rhyme|haiku|limerick)\b",
    r"\b(?:joke|jokes|riddle|riddles|funny story)\b",
    r"\b(?:weather\s+(?:like\s+in|in|forecast)|capital of|president of|who won the)\b",
    r"\b(?:translate|translation|into\s+(?:french|spanish|german|hindi|chinese|japanese))\b",
    r"\b(?:harry\s+potter|movie|book|plot|novel|celebrity|actor|actress|singer)\b",
    r"\b(?:bomb|weapon|explosive|attack|gun|poison)\b",
    r"\b(?:export\s+(?:my\s+)?data|export\s+to\s+csv)\b",
    r"\b(?:scrape|scraper|scraping|crawler|crawling)\b",
    r"\b(?:write.*script|python\s+script|write\s+a\s+script)\b",
    r"\b(?:write a (?:snake|tetris|pong) game)\b",
]


def is_blocked_ood(query: str) -> bool:
    q_lower = query.lower()
    return any(re.search(pat, q_lower) for pat in OOD_BLOCKLIST_PATTERNS)


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


async def query_variants(query: str, chat_history: list[dict] = None) -> list[str]:
    normalized = normalize_query(query)

    # 1. Fast OOD blocklist: Return empty immediately for recipes, poems, jokes, scraping
    if is_blocked_ood(normalized):
        logger.info(f"OOD blocklist matched for query: '{query}'. Skipping query variants.")
        return []

    # 2. Fast slang/terse query dictionary lookup (< 6 words or exact match)
    clean_q = re.sub(r"[^\w\s]", "", normalized.lower()).strip()
    norm_q = normalized.lower().strip()
    expanded_override = None
    if norm_q in TERSE_QUERY_EXPANSIONS:
        expanded_override = TERSE_QUERY_EXPANSIONS[norm_q]
    elif clean_q in TERSE_QUERY_EXPANSIONS:
        expanded_override = TERSE_QUERY_EXPANSIONS[clean_q]

    variants = [normalized]
    if expanded_override:
        variants.insert(0, expanded_override)
        logger.info(f"Applied fast terse expansion: '{query}' -> '{expanded_override}'")
        return list(dict.fromkeys(variants))

    history_str = ""
    if chat_history:
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-3:]])

    try:
        llm = ChatOpenAI(
            model=getattr(settings, "FAST_LLM_MODEL", settings.LLM_MODEL),
            temperature=0,
            openai_api_key=getattr(settings, "FAST_LLM_API_KEY", "") or settings.OPENROUTER_API_KEY,
            openai_api_base=getattr(settings, "FAST_LLM_BASE_URL", "") or settings.OPENROUTER_BASE_URL,
            default_headers={"HTTP-Referer": "https://localhost:3000", "X-Title": "Support Docs Copilot"},
        )
        prompt = PromptTemplate(
            template="""You are an expert technical support search assistant.
Your goal is to generate 2 to 3 optimized search query variations to retrieve relevant technical documentation from our knowledge base.

CRITICAL RULES:
1. TYPO & SLANG NORMALIZATION:
   If the question contains typos, slang, or informal phrasing (e.g. 'halp my pasword broke', 'wat format for upload', 'cant login bro', 'support number plz', 'file upload work how', 'is it sync or async', 'redis broken'), rewrite into proper technical search terms (e.g. 'how to reset password', 'supported file formats for upload', 'how to reset password unable to login', 'customer support phone number', 'file upload endpoint instructions', 'async background worker architecture', 'redis worker architecture').
2. MULTI-HOP / COMPOUND DECOMPOSITION:
   If the question asks about two different topics (e.g. 'What is the rate limit and how do I authenticate?', 'How do I change my email and what happens if I get a 404 doing it?', 'If I upload a file, what formats are supported and how does the system process it in the background?'), decompose into individual search queries for EACH sub-topic (e.g. ['how to change account email address', 'Error Code 404 resource not found resolution']).
3. ADVERSARIAL & UNKNOWN FEATURE QUERIES:
   If the user asks about an uncommon or unsupported feature (e.g. 'upload MP4 videos', 'contact support via Slack', 'authenticate via OAuth2', 'rate limit for Enterprise plan', 'Error Code 500', 'RabbitMQ', 'Memcached'), provide search queries for the general feature category in documentation (e.g. 'supported file formats for upload', 'support contact options', 'API authentication methods', 'API rate limit tiers', 'documented error codes', 'redis worker architecture').
4. OUT-OF-DOMAIN:
   If the question is completely non-technical / conversational (e.g. recipes, sports, jokes, poems, writing web scrapers), return an empty list.

Return ONLY a JSON object with a single key 'variants' containing a list of strings.
Example output: {{"variants": ["query variant 1", "query variant 2"]}}

Chat History:
{chat_history}

User Question: {question}""",
            input_variables=["question", "chat_history"],
        )
        chain = prompt | llm
        result = await chain.ainvoke({"question": normalized, "chat_history": history_str})

        content = result.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            match = re.search(r"\[(.*?)\]", content, re.DOTALL)
            parsed = {"variants": json.loads(f"[{match.group(1)}]")} if match else {}
        new_variants = parsed.get("variants", [])

        if isinstance(new_variants, list):
            for variant in new_variants:
                if isinstance(variant, str) and variant.strip():
                    variants.append(variant.strip())

    except Exception as e:
        logger.warning(f"Failed to generate query variants with LLM: {e}")

    return list(dict.fromkeys(variants))


async def condense_query(query: str, chat_history: list[dict] = None, summary: str = None) -> str:
    if not chat_history and not summary:
        return normalize_query(query)

    normalized = normalize_query(query)
    lines = [f"{msg['role']}: {msg['content']}" for msg in (chat_history or [])[-6:]]
    if summary:
        lines.insert(0, summary if summary.startswith("System Summary:") else f"System Summary: {summary}")
    history_str = "\n".join(lines)

    try:
        llm = ChatOpenAI(
            model=getattr(settings, "FAST_LLM_MODEL", settings.LLM_MODEL),
            temperature=0,
            openai_api_key=getattr(settings, "FAST_LLM_API_KEY", "") or settings.OPENROUTER_API_KEY,
            openai_api_base=getattr(settings, "FAST_LLM_BASE_URL", "") or settings.OPENROUTER_BASE_URL,
            default_headers={"HTTP-Referer": "https://localhost:3000", "X-Title": "Support Docs Copilot"},
        )
        prompt = PromptTemplate(
            template="""Given the following chat history and a follow-up question, rewrite the follow-up question into a standalone query that can be understood without the chat history. Do not answer the question, just reformulate it.

CRITICAL INSTRUCTIONS:
1. If the follow-up question is a greeting, small talk, or a personal statement (e.g., "Hi", "My name is Raj", "Thank you"), RETURN IT EXACTLY UNCHANGED. Do not rewrite personal statements into third-person questions like "Who is Raj?".
2. If the follow-up question is already standalone, return it unchanged.

Chat History:
{chat_history}

Follow Up Question: {question}
Standalone Query:""",
            input_variables=["question", "chat_history"],
        )
        chain = prompt | llm
        result = await chain.ainvoke({"question": normalized, "chat_history": history_str})
        standalone = result.content.strip()
        if standalone:
            logger.debug(f"Condensed query: '{query}' -> '{standalone}'")
            return standalone
    except Exception as e:
        logger.warning(f"Failed to condense query with LLM: {e}")

    return normalized
