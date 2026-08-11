"""Model routing: a rate-limit-aware failover chain of free-tier providers.

Order: Gemini Flash (1.5k req/day, primary) → Groq Qwen3.6-27B (vision-capable,
verified empirically). A provider that errors — 429, quota, outage — is skipped
for that call and the next link serves it. Zero providers configured is still a
valid state: Argus degrades to DOM-only auditing.
"""
import json
from functools import lru_cache

from argus import config


class VisionUnavailable(Exception):
    """Every provider in the chain failed (or none are configured)."""


@lru_cache(maxsize=1)
def _chain() -> list[tuple[str, object]]:
    chain: list[tuple[str, object]] = []
    if config.DISABLE_VISION:
        return chain
    # max_retries=1: when a provider rate-limits, fail over to the next link
    # fast instead of sitting through minutes of exponential backoff.
    if config.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI

        chain.append(("gemini", ChatGoogleGenerativeAI(
            model=config.VISION_MODEL, temperature=0, max_retries=1, timeout=60)))
    if config.GROQ_API_KEY:
        from langchain_groq import ChatGroq

        chain.append(("groq", ChatGroq(
            model=config.GROQ_VISION_MODEL, temperature=0, max_retries=1, timeout=60)))
    if config.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI

        chain.append(("gemini-lite", ChatGoogleGenerativeAI(
            model=config.VISION_MODEL_FALLBACK, temperature=0, max_retries=1, timeout=60)))
    return chain


def has_vision() -> bool:
    return bool(_chain())


def text_of(content) -> str:
    """Model content may be a plain string or a list of typed content blocks."""
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def parse_json_array(text: str) -> list:
    """Extract the outermost JSON array, tolerating fences and preamble."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def invoke_vision(messages) -> tuple[str, str]:
    """Walk the chain; return (response text, provider name that served it)."""
    errors = []
    for name, model in _chain():
        try:
            return text_of(model.invoke(messages).content), name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise VisionUnavailable("; ".join(errors) or "no vision provider configured")
