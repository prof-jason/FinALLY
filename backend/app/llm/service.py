"""Chat orchestration: context -> LLM (or mock) -> auto-execution -> persistence."""

from __future__ import annotations

import inspect
from typing import Any

from app import db, services

from .client import call_llm
from .mock import is_mock_enabled, mock_chat_response
from .prompt import build_messages, build_portfolio_context
from .schemas import ChatResponse, TradeInstruction, WatchlistInstruction

HISTORY_LIMIT = 5


async def _maybe_await(value: Any) -> Any:
    """Service functions may be sync or async; support both."""
    if inspect.isawaitable(value):
        return await value
    return value


def _error_text(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc) or type(exc).__name__


async def _apply_watchlist_change(change: WatchlistInstruction) -> dict[str, Any]:
    ticker = change.ticker.strip().upper()
    result: dict[str, Any] = {"ticker": ticker, "action": change.action}
    try:
        if change.action == "add":
            await _maybe_await(services.add_watchlist_ticker(ticker))
        else:
            await _maybe_await(services.remove_watchlist_ticker(ticker))
    except Exception as exc:
        result.update(status="failed", error=_error_text(exc))
    else:
        result["status"] = "executed"
    return result


async def _apply_trade(trade: TradeInstruction) -> dict[str, Any]:
    ticker = trade.ticker.strip().upper()
    result: dict[str, Any] = {"ticker": ticker, "side": trade.side, "quantity": trade.quantity}
    try:
        outcome = await _maybe_await(services.execute_trade(ticker, trade.side, trade.quantity))
    except Exception as exc:
        result.update(status="failed", error=_error_text(exc))
    else:
        result.update(status="executed", price=outcome["trade"]["price"])
    return result


async def execute_actions(response: ChatResponse) -> dict[str, list[dict[str, Any]]]:
    """Watchlist changes first, then trades, each in order and independent of the others."""
    watchlist_changes = [await _apply_watchlist_change(c) for c in response.watchlist_changes]
    trades = [await _apply_trade(t) for t in response.trades]
    return {"trades": trades, "watchlist_changes": watchlist_changes}


def load_history(limit: int = HISTORY_LIMIT) -> list[dict[str, Any]]:
    with db.get_connection() as conn:
        return db.list_recent_chat(conn, limit=limit)


async def build_llm_messages(user_message: str) -> list[dict[str, str]]:
    portfolio = await _maybe_await(services.get_portfolio())
    watchlist = await _maybe_await(services.get_watchlist())
    context = build_portfolio_context(portfolio, watchlist)
    return build_messages(context, load_history(), user_message)


async def handle_chat(user_message: str) -> dict[str, Any]:
    """Process one chat turn and return the PLAN §8 Chat Response Contract.

    Raises client.LLMUnavailableError if the model can't be reached; nothing is
    persisted in that case.
    """
    if is_mock_enabled():
        response = mock_chat_response(user_message)
    else:
        response = await call_llm(await build_llm_messages(user_message))

    actions = await execute_actions(response)

    with db.transaction() as conn:
        db.insert_chat_message(conn, "user", user_message, None)
        db.insert_chat_message(conn, "assistant", response.message, actions)

    return {"message": response.message, "actions": actions}
