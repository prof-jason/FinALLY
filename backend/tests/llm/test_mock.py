"""LLM_MOCK deterministic responses."""

import pytest

from app.llm.mock import MOCK_DEFAULT_MESSAGE, is_mock_enabled, mock_chat_response


def test_default_message_without_commands():
    r = mock_chat_response("How is my portfolio doing?")
    assert r.message == MOCK_DEFAULT_MESSAGE
    assert r.trades == [] and r.watchlist_changes == []


def test_buy_and_sell_case_insensitive():
    r = mock_chat_response("Please BUY 10 aapl and then sell 2.5 Tsla")
    assert [(t.ticker, t.side, t.quantity) for t in r.trades] == [
        ("AAPL", "buy", 10.0),
        ("TSLA", "sell", 2.5),
    ]
    assert r.message != MOCK_DEFAULT_MESSAGE


def test_add_and_remove():
    r = mock_chat_response("add PYPL and Remove nflx")
    assert [(c.ticker, c.action) for c in r.watchlist_changes] == [
        ("PYPL", "add"),
        ("NFLX", "remove"),
    ]
    assert r.trades == []


def test_mixed_commands_deterministic():
    msg = "buy 5 MSFT, add PYPL"
    assert mock_chat_response(msg) == mock_chat_response(msg)
    r = mock_chat_response(msg)
    assert len(r.trades) == 1 and len(r.watchlist_changes) == 1


@pytest.mark.parametrize(
    "value,expected", [("true", True), ("TRUE", True), ("false", False), ("", False), ("1", False)]
)
def test_is_mock_enabled(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_MOCK", value)
    assert is_mock_enabled() is expected


def test_is_mock_enabled_unset(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert is_mock_enabled() is False
