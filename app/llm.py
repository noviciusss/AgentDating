"""
LLM wrapper — provider-agnostic, rate-limited, with failover.

Uses AsyncOpenAI against any OpenAI-compatible endpoint.
Enforces global RPM limit, retries on 429/5xx, fails over to fallback.
Parses JSON tolerantly (strips code fences, prose wrapping).
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import (
    LLM_BASE_URL, LLM_API_KEY, ANALYSIS_MODEL, DATE_MODEL,
    FALLBACK_BASE_URL, FALLBACK_API_KEY, FALLBACK_MODEL,
    LLM_RPM,
)

logger = logging.getLogger(__name__)

# ── Rate limiter ───────────────────────────────────────────────────

class RateLimiter:
    """Token-bucket style rate limiter for requests per minute."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.interval = 60.0 / rpm if rpm > 0 else 0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self.interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


_rate_limiter = RateLimiter(LLM_RPM)

# ── Clients ────────────────────────────────────────────────────────

_primary_client: Optional[AsyncOpenAI] = None
_fallback_client: Optional[AsyncOpenAI] = None


def _get_primary_client() -> AsyncOpenAI:
    global _primary_client
    if _primary_client is None:
        _primary_client = AsyncOpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            default_headers={"accept-encoding": "identity"},
            max_retries=0,
        )
    return _primary_client


def _get_fallback_client() -> Optional[AsyncOpenAI]:
    global _fallback_client
    if not FALLBACK_API_KEY:
        return None
    if _fallback_client is None:
        _fallback_client = AsyncOpenAI(
            base_url=FALLBACK_BASE_URL,
            api_key=FALLBACK_API_KEY,
            default_headers={"accept-encoding": "identity"},
            max_retries=0,
        )
    return _fallback_client


# ── JSON parsing ───────────────────────────────────────────────────

def parse_llm_json(text: str) -> dict:
    """Tolerantly parse JSON from LLM output.
    Handles code fences, prose wrapping, and common issues.
    """
    text = text.strip()

    # Strip code fences
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try to find JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


# ── Core call ──────────────────────────────────────────────────────

_consecutive_primary_failures = 0
_MAX_PRIMARY_FAILURES = 3  # Switch to fallback after this many 429s


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    json_mode: bool = False,
    return_model: bool = False,
) -> Any:
    """Make an LLM call with rate limiting, retries, and failover.

    Returns the raw response text (or tuple (content, model) if return_model=True).
    Use parse_llm_json() to extract JSON.
    """
    global _consecutive_primary_failures

    if not model:
        model = ANALYSIS_MODEL

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # Decide which client to try first
    use_fallback_first = _consecutive_primary_failures >= _MAX_PRIMARY_FAILURES
    primary_client = _get_primary_client()
    fb = _get_fallback_client()

    # Determine fallback models on Groq
    groq_models = [model]
    for alt in ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
        if alt not in groq_models:
            groq_models.append(alt)

    clients_to_try = []
    if use_fallback_first and fb:
        clients_to_try.append(("fallback", fb, FALLBACK_MODEL or model))

    for m in groq_models:
        clients_to_try.append(("primary", primary_client, m))

    if not use_fallback_first and fb:
        clients_to_try.append(("fallback", fb, FALLBACK_MODEL or model))

    last_error = None
    for provider_name, client, use_model in clients_to_try:
        for attempt in range(2):  # retry once
            try:
                await _rate_limiter.acquire()
                call_kwargs = {**kwargs, "model": use_model}
                if "qwen" in use_model and call_kwargs.get("max_tokens", 0) > 1000:
                    call_kwargs["max_tokens"] = 1000

                response = await client.chat.completions.create(**call_kwargs)
                content = response.choices[0].message.content or ""

                # Reset failure counter on success
                if provider_name == "primary":
                    _consecutive_primary_failures = 0

                if return_model:
                    return content, use_model
                return content

            except Exception as e:
                last_error = e
                err_str = str(e)
                status = getattr(e, 'status_code', 0) or 0

                logger.warning(
                    f"LLM call failed ({provider_name}, attempt {attempt + 1}): "
                    f"status={status} error={err_str[:200]}"
                )

                # Retry without json_object constraint if model rejected it
                if ("json_validate_failed" in err_str.lower() or "failed to validate json" in err_str.lower()) and "response_format" in call_kwargs:
                    logger.info(f"Retrying {use_model} without response_format constraint...")
                    call_kwargs.pop("response_format", None)
                    try:
                        await _rate_limiter.acquire()
                        response = await client.chat.completions.create(**call_kwargs)
                        content = response.choices[0].message.content or ""
                        if provider_name == "primary":
                            _consecutive_primary_failures = 0
                        if return_model:
                            return content, use_model
                        return content
                    except Exception as inner_e:
                        last_error = inner_e
                        err_str = str(inner_e)

                if provider_name == "primary" and (status == 429 or status >= 500):
                    _consecutive_primary_failures += 1

                # Check for Retry-After header
                retry_after = None
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    retry_after = e.response.headers.get('Retry-After')

                if "tpd" in err_str.lower() or "tokens per day" in err_str.lower() or status == 413:
                    logger.info(f"Model {use_model} reached daily limit or prompt too large, immediately switching to next model.")
                    break

                if status == 429:
                    if attempt == 0:
                        wait = float(retry_after) if retry_after else 25.0
                        logger.info(f"Model {use_model} hit 429 rate limit. Waiting {wait:.1f}s for bucket reset...")
                        await asyncio.sleep(min(wait, 35))
                    else:
                        break

                if attempt == 0:
                    wait = float(retry_after) if retry_after else (2 ** attempt * 2)
                    await asyncio.sleep(min(wait, 15))
                else:
                    break  # Move to next provider

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


async def call_llm_with_messages(
    messages: list[dict],
    model: str = "",
    max_tokens: int = 150,
    temperature: float = 0.9,
    return_model: bool = False,
) -> Any:
    """Make an LLM call with a full message list (used for date turns).
    Same retry/failover logic as call_llm.
    """
    global _consecutive_primary_failures

    if not model:
        model = DATE_MODEL

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    use_fallback_first = _consecutive_primary_failures >= _MAX_PRIMARY_FAILURES
    primary_client = _get_primary_client()
    fb = _get_fallback_client()

    groq_models = [model]
    for alt in ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
        if alt not in groq_models:
            groq_models.append(alt)

    clients_to_try = []
    if use_fallback_first and fb:
        clients_to_try.append(("fallback", fb, FALLBACK_MODEL or model))

    for m in groq_models:
        clients_to_try.append(("primary", primary_client, m))

    if not use_fallback_first and fb:
        clients_to_try.append(("fallback", fb, FALLBACK_MODEL or model))

    last_error = None
    for provider_name, client, use_model in clients_to_try:
        for attempt in range(2):
            try:
                await _rate_limiter.acquire()
                call_kwargs = {**kwargs, "model": use_model}
                response = await client.chat.completions.create(**call_kwargs)
                content = response.choices[0].message.content or ""

                if provider_name == "primary":
                    _consecutive_primary_failures = 0

                if return_model:
                    return content, use_model
                return content

            except Exception as e:
                last_error = e
                status = getattr(e, 'status_code', 0) or 0
                logger.warning(
                    f"LLM call failed ({provider_name}, attempt {attempt + 1}): "
                    f"status={status}"
                )
                if provider_name == "primary" and (status == 429 or status >= 500):
                    _consecutive_primary_failures += 1

                retry_after = None
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    retry_after = e.response.headers.get('Retry-After')

                err_str = str(e)
                if "tpd" in err_str.lower() or "tokens per day" in err_str.lower() or status == 413 or status == 429:
                    logger.info(f"Model {use_model} hit rate limit ({status}), immediately switching to next model.")
                    break

                if attempt == 0:
                    wait = float(retry_after) if retry_after else (2 ** attempt * 2)
                    await asyncio.sleep(min(wait, 15))
                else:
                    break

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
