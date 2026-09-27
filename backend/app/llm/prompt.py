"""System prompt, portfolio context and message assembly for the chat LLM."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant inside a simulated trading \
workstation. The user trades a virtual portfolio with fake money; market orders fill \
instantly at the current price.

Your job:
- Analyze portfolio composition, risk concentration, and P&L using the context provided.
- Suggest trades with brief, data-driven reasoning.
- Execute trades when the user asks for them or agrees to your suggestion, by listing \
them in "trades".
- Manage the watchlist proactively via "watchlist_changes" (add or remove tickers) when \
it helps the user.
- Be concise: a few short sentences or a compact list. Cite numbers from the context.

Rules:
- Never short sell or use margin: only sell shares the user holds (up to the held \
quantity), and only buy what available cash covers at current prices.
- Tickers are 1-5 uppercase letters (e.g. AAPL). Quantities must be > 0; fractional \
shares are allowed.
- Your message is written BEFORE anything executes, so phrase trades and watchlist \
changes as intentions ("Placing an order for 10 AAPL..."), never as confirmed fills.
- Only include trades / watchlist changes you actually intend to execute now. If the \
user is just asking a question, leave both lists empty.
- Previous assistant turns may include the results of their actions (executed or \
failed with an error). Acknowledge failures when relevant.

Always respond with valid JSON matching this schema and nothing else:
{"message": "<your reply to the user>",
 "trades": [{"ticker": "AAPL", "side": "buy" | "sell", "quantity": 10}],
 "watchlist_changes": [{"ticker": "PYPL", "action": "add" | "remove"}]}"""


def _fmt_money(value: Any) -> str:
    return "n/a" if value is None else f"${value:,.2f}"


def _fmt_pct(value: Any) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def build_portfolio_context(portfolio: dict[str, Any], watchlist: list[dict[str, Any]]) -> str:
    """Render the user's current state as compact text for the LLM."""
    lines = [
        "Current portfolio state:",
        f"- Cash: {_fmt_money(portfolio.get('cash_balance'))}",
        f"- Total value: {_fmt_money(portfolio.get('total_value'))}",
        f"- Total unrealized P&L: {_fmt_money(portfolio.get('total_unrealized_pnl'))}",
    ]

    positions = portfolio.get("positions") or []
    total = portfolio.get("total_value") or 0
    if positions:
        lines.append("Positions:")
        for p in positions:
            weight = (
                f"{p['market_value'] / total * 100:.1f}% of portfolio"
                if total and p.get("market_value") is not None
                else "weight n/a"
            )
            lines.append(
                f"- {p['ticker']}: {p['quantity']:g} shares, avg cost "
                f"{_fmt_money(p.get('avg_cost'))}, price {_fmt_money(p.get('current_price'))}, "
                f"value {_fmt_money(p.get('market_value'))} ({weight}), unrealized P&L "
                f"{_fmt_money(p.get('unrealized_pnl'))} "
                f"({_fmt_pct(p.get('unrealized_pnl_percent'))})"
            )
    else:
        lines.append("Positions: none")

    if watchlist:
        lines.append("Watchlist (live prices):")
        for w in watchlist:
            lines.append(
                f"- {w['ticker']}: {_fmt_money(w.get('price'))} "
                f"({_fmt_pct(w.get('change_percent'))} since last tick)"
            )
    else:
        lines.append("Watchlist: empty")
    return "\n".join(lines)


def _history_content(msg: dict[str, Any]) -> str:
    content = msg.get("content") or ""
    actions = msg.get("actions")
    if msg.get("role") == "assistant" and actions and any(actions.values()):
        content += "\n\n[Action results: " + json.dumps(actions, separators=(",", ":")) + "]"
    return content


def build_messages(
    context: str, history: list[dict[str, Any]], user_message: str
) -> list[dict[str, str]]:
    """System prompt + portfolio context, then prior turns (oldest first), then the new message."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
    ]
    for msg in history:
        role = msg.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": _history_content(msg)})
    messages.append({"role": "user", "content": user_message})
    return messages
