"""
Unified LLM provider with automatic failover.

Priority order:
  1. Ollama (local, free, unlimited, private — code never leaves your machine)
  2. Groq  (cloud, fast, free tier has daily token limits)
  3. Gemini (cloud, fallback, free tier has rate limits)

If Ollama is running locally, it's always used first — zero cost, zero rate limits.
Cloud providers are only tried if Ollama isn't available.
"""

import os
import time
import asyncio
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.0-flash"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2
LLM_TIMEOUT = 120


class LLMProviderError(Exception):
    pass


class QuotaExceededError(LLMProviderError):
    pass


def _get_ollama():
    """Returns an Ollama LLM if the server is reachable."""
    try:
        from langchain_ollama import ChatOllama
        import urllib.request
        urllib.request.urlopen(OLLAMA_BASE_URL, timeout=2)
        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            timeout=LLM_TIMEOUT,
        )
    except ImportError:
        return None
    except Exception:
        return None


def _get_groq():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    return ChatGroq(api_key=key, model=GROQ_MODEL, temperature=0, timeout=30, max_retries=0)


def _get_gemini():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    return ChatGoogleGenerativeAI(
        google_api_key=key, model=GEMINI_MODEL, temperature=0, timeout=30, max_retries=0,
    )


def _is_quota_error(e: Exception) -> bool:
    s = str(e).lower()
    return "429" in s or "quota" in s or "rate_limit" in s or "resource exhausted" in s


def _invoke_with_retry(llm, prompt: str, provider_name: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            if _is_quota_error(e):
                raise QuotaExceededError(f"{provider_name} quota exceeded")
            last_err = e
            print(f"  [{provider_name}] attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise LLMProviderError(f"{provider_name} exhausted retries: {last_err}")


async def _ainvoke_with_retry(llm, prompt: str, provider_name: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=LLM_TIMEOUT)
            return response.content.strip()
        except asyncio.TimeoutError:
            last_err = f"Timeout after {LLM_TIMEOUT}s"
            print(f"  [{provider_name}] attempt {attempt}/{MAX_RETRIES} timed out")
        except Exception as e:
            if _is_quota_error(e):
                raise QuotaExceededError(f"{provider_name} quota exceeded")
            last_err = e
            print(f"  [{provider_name}] attempt {attempt}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise LLMProviderError(f"{provider_name} exhausted retries: {last_err}")


# --- Provider chain: Ollama → Groq → Gemini ---

PROVIDERS = [
    ("Ollama", _get_ollama),
    ("Groq", _get_groq),
    ("Gemini", _get_gemini),
]


def get_llm_response(prompt: str) -> str:
    """Sync call. Tries Ollama -> Groq -> Gemini."""
    for name, get_fn in PROVIDERS:
        llm = get_fn()
        if llm is None:
            continue
        try:
            return _invoke_with_retry(llm, prompt, name)
        except LLMProviderError as e:
            print(f"  [{name}] failed: {e}")
            continue

    raise LLMProviderError("No LLM provider available")


async def aget_llm_response(prompt: str) -> str:
    """Async call. Tries Ollama -> Groq -> Gemini."""
    for name, get_fn in PROVIDERS:
        llm = get_fn()
        if llm is None:
            continue
        try:
            return await _ainvoke_with_retry(llm, prompt, name)
        except LLMProviderError as e:
            print(f"  [{name}] failed: {e}")
            continue

    return "Unable to complete review — all LLM providers failed. Check Ollama/API keys."
