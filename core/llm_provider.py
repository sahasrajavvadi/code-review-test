"""
Unified LLM provider with automatic failover.

Why this exists:
Groq's free tier rate-limits hard and occasionally throws 503s. Instead of
the whole review pipeline dying when that happens, every agent calls
`get_llm_response()` which transparently tries Groq first and falls back to
Gemini (also free tier) if Groq fails or isn't configured. This is the
difference between "demo broke during the interview" and "system handled it".
"""

import os
import time
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

# Models — keep one source of truth so we're not hunting through 4 files
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2


class LLMProviderError(Exception):
    """Raised when ALL providers fail. Lets callers decide how to degrade."""
    pass


def _get_groq():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    return ChatGroq(api_key=key, model=GROQ_MODEL, temperature=0, timeout=30)


def _get_gemini():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    return ChatGoogleGenerativeAI(
        google_api_key=key, model=GEMINI_MODEL, temperature=0, timeout=30
    )


def _invoke_with_retry(llm, prompt: str, provider_name: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            last_err = e
            print(f"⚠️  {provider_name} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise LLMProviderError(f"{provider_name} exhausted retries: {last_err}")


async def _ainvoke_with_retry(llm, prompt: str, provider_name: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            last_err = e
            print(f"⚠️  {provider_name} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise LLMProviderError(f"{provider_name} exhausted retries: {last_err}")


def get_llm_response(prompt: str) -> str:
    """Sync call used by agents. Tries Groq, falls back to Gemini."""
    groq = _get_groq()
    if groq is not None:
        try:
            return _invoke_with_retry(groq, prompt, "Groq")
        except LLMProviderError as e:
            print(f"🔁 Groq failed, falling back to Gemini: {e}")

    gemini = _get_gemini()
    if gemini is not None:
        try:
            return _invoke_with_retry(gemini, prompt, "Gemini")
        except LLMProviderError as e:
            print(f"❌ Gemini also failed: {e}")

    raise LLMProviderError(
        "No LLM provider available — check GROQ_API_KEY / GEMINI_API_KEY"
    )


async def aget_llm_response(prompt: str) -> str:
    """Async call used by agents running in parallel via asyncio.gather."""
    groq = _get_groq()
    if groq is not None:
        try:
            return await _ainvoke_with_retry(groq, prompt, "Groq")
        except LLMProviderError as e:
            print(f"🔁 Groq failed, falling back to Gemini: {e}")

    gemini = _get_gemini()
    if gemini is not None:
        try:
            return await _ainvoke_with_retry(gemini, prompt, "Gemini")
        except LLMProviderError as e:
            print(f"❌ Gemini also failed: {e}")

    raise LLMProviderError(
        "No LLM provider available — check GROQ_API_KEY / GEMINI_API_KEY"
    )
