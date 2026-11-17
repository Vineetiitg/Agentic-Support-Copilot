import re
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Secret & Credential Regex Patterns
PII_SECRET_PATTERNS = [
    (re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{25,}\b", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE), r"\1[REDACTED_PASSWORD]\2"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10}|\d{3}[-.\s]\d{3}[-.\s]\d{4})\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_CC]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
]

# Lazy-loaded Presidio engines
_presidio_analyzer = None
_presidio_anonymizer = None
_presidio_initialized = False


def _get_presidio_engines():
    global _presidio_analyzer, _presidio_anonymizer, _presidio_initialized
    if _presidio_initialized:
        return _presidio_analyzer, _presidio_anonymizer

    _presidio_initialized = True
    if not getattr(settings, "ENABLE_PRESIDIO", True):
        return None, None

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _presidio_analyzer = AnalyzerEngine()
        _presidio_anonymizer = AnonymizerEngine()
        logger.info("Microsoft Presidio PII Engine initialized successfully.")
    except Exception as exc:
        logger.debug(f"Presidio not available ({exc}); using regex PII scrubber.")
        _presidio_analyzer = None
        _presidio_anonymizer = None

    return _presidio_analyzer, _presidio_anonymizer


def redact_sensitive_data(text: str) -> str:
    """
    Tier 3 Output Guardrail:
    1. Runs Microsoft Presidio NLP Analyzer + Anonymizer (for PERSON, EMAIL, PHONE, LOCATION) if available.
    2. Runs deterministic regex pattern masking for API keys, tokens, passwords, and numbers.
    """
    if not text:
        return ""

    redacted = text

    # Step 1: Microsoft Presidio (NLP-based PII redaction)
    analyzer, anonymizer = _get_presidio_engines()
    if analyzer and anonymizer:
        try:
            results = analyzer.analyze(
                text=redacted,
                entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "IP_ADDRESS"],
                language="en",
            )
            if results:
                anonymized_result = anonymizer.anonymize(text=redacted, analyzer_results=results)
                redacted = anonymized_result.text
        except Exception as exc:
            logger.debug(f"Presidio anonymization error: {exc}")

    # Step 2: Deterministic Secret & Credential Regex Scrubber
    for pattern, replacement in PII_SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return redacted


def refuses_system_prompt_leak(text: str) -> bool:
    normalized = text.lower()
    return "system prompt" in normalized or "developer message" in normalized

