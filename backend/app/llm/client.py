"""LiteLLM -> OpenRouter call. Only the free Nemotron model is ever used."""

from __future__ import annotations

import asyncio
import logging

from litellm import completion

from .schemas import ChatResponse, MalformedResponseError, parse_chat_response

logger = logging.getLogger(__name__)

MODEL = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
REQUEST_TIMEOUT_SECONDS = 90


class LLMUnavailableError(RuntimeError):
    """The LLM call failed (network, rate limit, auth, unusable output)."""


def _call_completion(messages: list[dict[str, str]]) -> str | None:
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return response.choices[0].message.content


async def call_llm(messages: list[dict[str, str]]) -> ChatResponse:
    """Run the blocking LiteLLM call in a worker thread and parse the structured reply."""
    try:
        content = await asyncio.to_thread(_call_completion, messages)
    except Exception as exc:  # litellm raises many provider-specific error types
        logger.warning("LLM call failed: %s: %s", type(exc).__name__, exc)
        raise LLMUnavailableError(str(exc)) from exc
    try:
        return parse_chat_response(content)
    except MalformedResponseError as exc:
        logger.warning("Unusable LLM response: %r", content)
        raise LLMUnavailableError(str(exc)) from exc
