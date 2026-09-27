"""Structured-output schema for the LLM and lenient parsing of its replies."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class TradeInstruction(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistInstruction(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """What the LLM must return (passed to LiteLLM as `response_format`)."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistInstruction] = Field(default_factory=list)


class MalformedResponseError(ValueError):
    """The LLM reply could not be interpreted at all."""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Find a JSON object in `text`: the whole string, a ``` fence, or the outermost {...}."""
    candidates = [text]
    candidates += _FENCE_RE.findall(text)
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_item(item: Any) -> Any:
    """Lowercase enum-like fields so "BUY" / "Add" still validate."""
    if not isinstance(item, dict):
        return item
    item = dict(item)
    for key in ("side", "action"):
        if isinstance(item.get(key), str):
            item[key] = item[key].strip().lower()
    return item


def parse_chat_response(content: str | None) -> ChatResponse:
    """Parse an LLM reply as leniently as is safe.

    - Valid JSON matching the schema is used as-is.
    - JSON wrapped in prose or code fences is extracted.
    - Individual malformed trade / watchlist items are dropped; the rest survive.
    - Non-JSON text becomes the message with no actions.
    - Empty content raises MalformedResponseError.
    """
    if content is None or not content.strip():
        raise MalformedResponseError("Empty response from the AI model")

    try:
        return ChatResponse.model_validate_json(content)
    except ValidationError:
        pass

    data = _extract_json_object(content)
    if data is None:
        return ChatResponse(message=content.strip())

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        message = "" if message is None else str(message)

    trades: list[TradeInstruction] = []
    for item in _as_list(data.get("trades")):
        try:
            trades.append(TradeInstruction.model_validate(_normalize_item(item)))
        except ValidationError:
            continue

    changes: list[WatchlistInstruction] = []
    for item in _as_list(data.get("watchlist_changes")):
        try:
            changes.append(WatchlistInstruction.model_validate(_normalize_item(item)))
        except ValidationError:
            continue

    if not message and not trades and not changes:
        raise MalformedResponseError("AI response did not contain a message")
    return ChatResponse(message=message, trades=trades, watchlist_changes=changes)
