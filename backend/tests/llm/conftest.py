"""Fakes for app.services / app.db so chat tests never touch the network or real state."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.llm import client, service


class FakeServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FakeServices:
    """Minimal in-memory portfolio that enforces the PLAN §8 trade rules."""

    def __init__(self) -> None:
        self.cash = 10000.0
        self.prices = {"AAPL": 190.0, "TSLA": 250.0, "MSFT": 400.0}
        self.positions: dict[str, dict] = {}
        self.watchlist = ["AAPL", "TSLA", "MSFT"]
        self.calls: list[tuple] = []

    def execute_trade(self, ticker, side, quantity):
        self.calls.append(("trade", ticker, side, quantity))
        if quantity <= 0:
            raise FakeServiceError("Quantity must be greater than 0")
        price = self.prices.get(ticker)
        if price is None:
            raise FakeServiceError(f"No price available for {ticker}")
        pos = self.positions.get(ticker)
        if side == "buy":
            if quantity * price > self.cash:
                raise FakeServiceError("Insufficient cash")
            self.cash -= quantity * price
            held = pos["quantity"] if pos else 0.0
            self.positions[ticker] = {
                "ticker": ticker,
                "quantity": held + quantity,
                "avg_cost": price,
            }
        else:
            if not pos or quantity > pos["quantity"] + 1e-9:
                raise FakeServiceError("Insufficient shares")
            self.cash += quantity * price
            pos["quantity"] -= quantity
            if abs(pos["quantity"]) < 1e-9:
                del self.positions[ticker]
        trade = {
            "id": "t1",
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": "2026-09-27T00:00:00Z",
        }
        return {"trade": trade, "portfolio": self.get_portfolio()}

    async def add_watchlist_ticker(self, ticker):  # async, like a source.add_ticker call
        self.calls.append(("add", ticker))
        if not ticker.isalpha() or len(ticker) > 5:
            raise FakeServiceError(f"Invalid ticker: {ticker!r}")
        if ticker not in self.watchlist:
            self.watchlist.append(ticker)
        return {"ticker": ticker}

    def remove_watchlist_ticker(self, ticker):
        self.calls.append(("remove", ticker))
        if ticker not in self.watchlist:
            raise FakeServiceError(f"{ticker} is not on the watchlist", 404)
        self.watchlist.remove(ticker)

    def get_portfolio(self):
        positions = []
        for p in self.positions.values():
            price = self.prices[p["ticker"]]
            mv = p["quantity"] * price
            pnl = (price - p["avg_cost"]) * p["quantity"]
            cost = p["avg_cost"] * p["quantity"]
            positions.append(
                {
                    **p,
                    "current_price": price,
                    "market_value": mv,
                    "unrealized_pnl": pnl,
                    "unrealized_pnl_percent": pnl / cost * 100,
                }
            )
        total = self.cash + sum(p["market_value"] for p in positions)
        return {
            "cash_balance": self.cash,
            "total_value": total,
            "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in positions),
            "positions": positions,
        }

    def get_watchlist(self):
        return [
            {"ticker": t, "price": self.prices.get(t), "change_percent": 0.1}
            for t in self.watchlist
        ]


class FakeDB:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.list_limits: list[int] = []

    @contextmanager
    def get_connection(self):
        yield "conn"

    @contextmanager
    def transaction(self, conn=None):
        yield "conn"

    def insert_chat_message(self, conn, role, content, actions, user_id="default"):
        self.messages.append({"role": role, "content": content, "actions": copy.deepcopy(actions)})

    def list_recent_chat(self, conn, limit=5, user_id="default"):
        self.list_limits.append(limit)
        return copy.deepcopy(self.messages[-limit:])


@pytest.fixture
def fake_services(monkeypatch):
    fake = FakeServices()
    monkeypatch.setattr(service, "services", fake)
    return fake


@pytest.fixture
def fake_db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(service, "db", fake)
    return fake


@pytest.fixture
def llm_reply(monkeypatch):
    """Monkeypatch litellm.completion; set `.content` to control the reply, inspect `.calls`."""
    state = SimpleNamespace(
        content='{"message": "ok", "trades": [], "watchlist_changes": []}', calls=[], error=None
    )

    def fake_completion(**kwargs):
        state.calls.append(kwargs)
        if state.error is not None:
            raise state.error
        msg = SimpleNamespace(content=state.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(client, "completion", fake_completion)
    monkeypatch.setenv("LLM_MOCK", "false")
    return state
