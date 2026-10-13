import json
import re

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import logger


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


async def query_variants(query: str, chat_history: list[dict] = None) -> list[str]:
    normalized = normalize_query(query)
    variants = [normalized]
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
   If the question contains typos, slang, or informal phrasing (e.g. 'halp my pasword broke', 'wat format for upload', 'cant login bro', 'support number plz', 'file upload work how', 'is it sync or async'), rewrite into proper technical search terms (e.g. 'how to reset password', 'supported file formats for upload', 'trouble logging in authentication', 'customer support phone number', 'file upload endpoint instructions', 'async background worker architecture').
2. MULTI-HOP DECOMPOSITION:
   If the question asks about two different topics (e.g. 'What is the rate limit and how do I authenticate?', 'How to change email and what if 404 error?'), provide individual search queries for EACH sub-topic so documents for both can be retrieved.
3. ADVERSARIAL & UNKNOWN FEATURE QUERIES:
   If the user asks about an uncommon or unsupported feature (e.g. 'upload MP4 videos', 'contact support via Slack', 'authenticate via OAuth2', 'rate limit for Enterprise plan'), provide search queries for the general feature category in documentation (e.g. 'supported file formats for upload', 'support contact options', 'API authentication methods', 'API rate limit').
4. OUT-OF-DOMAIN:
   If the question is completely non-technical / conversational (e.g. recipes, sports, jokes, poems), return an empty list.

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
