"""Deterministic mock LLM used when LLM_MOCK=true (E2E tests, offline development).

Contract (planning/TEAM_CONTRACTS.md):
- `buy <qty> <TICKER>` / `sell <qty> <TICKER>` (case-insensitive) emit that trade
- `add <TICKER>` / `remove <TICKER>` emit watchlist changes
- otherwise a fixed message with no actions
"""

from __future__ import annotations

import os
import re

from .schemas import ChatResponse, TradeInstruction, WatchlistInstruction

MOCK_DEFAULT_MESSAGE = "Mock response: I can help you analyze your portfolio."

_TRADE_RE = re.compile(r"\b(buy|sell)\s+(\d+(?:\.\d+)?)\s+([a-z]{1,5})\b", re.IGNORECASE)
_WATCH_RE = re.compile(r"\b(add|remove)\s+([a-z]{1,5})\b", re.IGNORECASE)


def is_mock_enabled() -> bool:
    """Read LLM_MOCK on every call so tests can toggle it."""
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def mock_chat_response(user_message: str) -> ChatResponse:
    trades = [
        TradeInstruction(ticker=ticker.upper(), side=side.lower(), quantity=float(qty))
        for side, qty, ticker in _TRADE_RE.findall(user_message)
    ]
    changes = [
        WatchlistInstruction(ticker=ticker.upper(), action=action.lower())
        for action, ticker in _WATCH_RE.findall(user_message)
    ]
    if not trades and not changes:
        return ChatResponse(message=MOCK_DEFAULT_MESSAGE)

    parts = [f"{t.side} {t.quantity:g} {t.ticker}" for t in trades]
    parts += [
        f"{c.action} {c.ticker} {'to' if c.action == 'add' else 'from'} watchlist" for c in changes
    ]
    message = "Mock response: placing your request: " + "; ".join(parts) + "."
    return ChatResponse(message=message, trades=trades, watchlist_changes=changes)
