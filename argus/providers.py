"""Model routing: free tiers first, graceful degradation to zero-key mode.

Phase 1 only needs the vision model (Gemini free tier). The Groq entry is the
start of the rate-limit-aware failover chain built out in Phase 2.
"""
from functools import lru_cache

from argus import config


@lru_cache(maxsize=1)
def vision_model():
    """Gemini Flash via free AI Studio key, or None → vision audits are skipped."""
    if not config.has_vlm():
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=config.VISION_MODEL, temperature=0)
