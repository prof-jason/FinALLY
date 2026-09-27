"""Repository functions: watchlist, positions, trades, snapshots, chat, reset."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.db import (
    DEFAULT_WATCHLIST,
    add_watchlist,
    delete_position,
    format_ts,
    get_cash,
    get_position,
    insert_chat_message,
    insert_snapshot,
    insert_trade,
    list_positions,
    list_recent_chat,
    list_snapshots,
    list_trades,
    list_watchlist,
    prune_snapshots,
    remove_watchlist,
    reset_user,
    set_cash,
    upsert_position,
    utc_now,
)


def _uuid_like(value: str) -> bool:
    return isinstance(value, str) and len(value) == 36 and value.count("-") == 4


def test_timestamp_format():
    ts = utc_now()
    assert ts.endswith("Z")
    assert datetime.fromisoformat(ts).tzinfo is not None
    assert format_ts(datetime(2026, 1, 2, 3, 4, 5, 678999)) == "2026-01-02T03:04:05.678Z"


# --- Cash ---------------------------------------------------------------------


def test_cash_roundtrip(conn):
    set_cash(conn, 2500.5)
    assert get_cash(conn) == 2500.5


def test_cash_unknown_user(conn):
    with pytest.raises(LookupError):
        get_cash(conn, user_id="nobody")
    with pytest.raises(LookupError):
        set_cash(conn, 1.0, user_id="nobody")


# --- Watchlist ----------------------------------------------------------------


def test_watchlist_add_and_remove(conn):
    assert add_watchlist(conn, "PYPL") is True
    tickers = [w["ticker"] for w in list_watchlist(conn)]
    assert tickers[-1] == "PYPL"
    assert len(tickers) == 11
    assert list_watchlist(conn)[-1]["added_at"].endswith("Z")

    assert add_watchlist(conn, "PYPL") is False  # duplicate
    assert len(list_watchlist(conn)) == 11

    assert remove_watchlist(conn, "PYPL") is True
    assert remove_watchlist(conn, "PYPL") is False
    assert "PYPL" not in [w["ticker"] for w in list_watchlist(conn)]


def test_watchlist_unique_constraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES ('x', 'default', "
            "'AAPL', '2026-01-01T00:00:00.000Z')"
        )


def test_watchlist_is_per_user(conn):
    assert add_watchlist(conn, "AAPL", user_id="other") is True
    assert [w["ticker"] for w in list_watchlist(conn, user_id="other")] == ["AAPL"]
    assert len(list_watchlist(conn)) == 10


# --- Positions ----------------------------------------------------------------


def test_position_upsert_get_delete(conn):
    assert get_position(conn, "AAPL") is None
    pos = upsert_position(conn, "AAPL", 2.5, 190.0)
    assert pos["ticker"] == "AAPL" and pos["quantity"] == 2.5 and pos["avg_cost"] == 190.0
    assert get_position(conn, "AAPL") == pos

    upsert_position(conn, "AAPL", 5.0, 195.0)
    stored = get_position(conn, "AAPL")
    assert stored["quantity"] == 5.0 and stored["avg_cost"] == 195.0
    assert conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 1

    assert delete_position(conn, "AAPL") is True
    assert delete_position(conn, "AAPL") is False
    assert get_position(conn, "AAPL") is None


def test_list_positions(conn):
    upsert_position(conn, "TSLA", 1, 250)
    upsert_position(conn, "AAPL", 0.25, 190)
    positions = list_positions(conn)
    assert [p["ticker"] for p in positions] == ["AAPL", "TSLA"]
    assert set(positions[0]) == {"ticker", "quantity", "avg_cost", "updated_at"}
    assert positions[0]["quantity"] == 0.25


def test_positions_unique_constraint(conn):
    upsert_position(conn, "AAPL", 1, 190)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES ('x', 'default', 'AAPL', 1, 1, '2026-01-01T00:00:00.000Z')"
        )


# --- Trades -------------------------------------------------------------------


def test_insert_trade_returns_dict(conn):
    trade = insert_trade(conn, "AAPL", "buy", 2.5, 191.23)
    assert _uuid_like(trade["id"])
    assert trade["ticker"] == "AAPL" and trade["side"] == "buy"
    assert trade["quantity"] == 2.5 and trade["price"] == 191.23
    assert trade["executed_at"].endswith("Z")
    assert list_trades(conn) == [trade]


def test_trades_newest_first_and_limit(conn):
    ids = [insert_trade(conn, "AAPL", "buy", i + 1, 100.0)["id"] for i in range(5)]
    trades = list_trades(conn)
    assert [t["id"] for t in trades] == list(reversed(ids))
    assert [t["id"] for t in list_trades(conn, limit=2)] == [ids[4], ids[3]]


def test_trade_side_check(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_trade(conn, "AAPL", "short", 1, 100.0)


# --- Snapshots ----------------------------------------------------------------


def test_snapshots_since_oldest_first(conn):
    now = datetime.now(UTC)
    insert_snapshot(conn, 3.0, recorded_at=now - timedelta(hours=1))
    insert_snapshot(conn, 1.0, recorded_at=now - timedelta(days=11))
    insert_snapshot(conn, 2.0, recorded_at=now - timedelta(days=2))
    snap = insert_snapshot(conn, 4.0)
    assert _uuid_like(snap["id"])

    assert [s["total_value"] for s in list_snapshots(conn)] == [1.0, 2.0, 3.0, 4.0]
    recent = list_snapshots(conn, since=now - timedelta(days=10))
    assert [s["total_value"] for s in recent] == [2.0, 3.0, 4.0]
    assert set(recent[0]) == {"total_value", "recorded_at"}
    # ISO string input works too
    assert len(list_snapshots(conn, since=format_ts(now - timedelta(days=3)))) == 3


def test_prune_snapshots_older_than_10_days(conn):
    now = datetime.now(UTC)
    insert_snapshot(conn, 1.0, recorded_at=now - timedelta(days=15))
    insert_snapshot(conn, 2.0, recorded_at=now - timedelta(days=10, minutes=1))
    insert_snapshot(conn, 3.0, recorded_at=now - timedelta(days=9))
    insert_snapshot(conn, 4.0)

    assert prune_snapshots(conn, now - timedelta(days=10)) == 2
    assert [s["total_value"] for s in list_snapshots(conn)] == [3.0, 4.0]
    assert prune_snapshots(conn, now - timedelta(days=10)) == 0


# --- Chat ---------------------------------------------------------------------


def test_chat_actions_json_roundtrip(conn):
    actions = {
        "trades": [
            {"ticker": "AAPL", "side": "buy", "quantity": 10, "status": "executed",
             "price": 191.23},
            {"ticker": "TSLA", "side": "buy", "quantity": 500, "status": "failed",
             "error": "Insufficient cash"},
        ],
        "watchlist_changes": [{"ticker": "PYPL", "action": "add", "status": "executed"}],
    }
    insert_chat_message(conn, "user", "buy stuff")
    msg = insert_chat_message(conn, "assistant", "Placing orders", actions)
    assert msg["actions"] == actions

    history = list_recent_chat(conn)
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["actions"] is None
    assert history[1]["actions"] == actions
    assert set(history[1]) == {"id", "role", "content", "actions", "created_at"}


def test_chat_last_five_oldest_first(conn):
    for i in range(8):
        insert_chat_message(conn, "user" if i % 2 == 0 else "assistant", f"m{i}")
    assert [m["content"] for m in list_recent_chat(conn)] == ["m3", "m4", "m5", "m6", "m7"]
    assert [m["content"] for m in list_recent_chat(conn, limit=2)] == ["m6", "m7"]


def test_chat_role_check(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_chat_message(conn, "system", "nope")


# --- Reset --------------------------------------------------------------------


def test_reset_restores_seed_state(conn):
    set_cash(conn, 1.0)
    remove_watchlist(conn, "AAPL")
    add_watchlist(conn, "PYPL")
    upsert_position(conn, "PYPL", 3, 60)
    insert_trade(conn, "PYPL", "buy", 3, 60)
    insert_snapshot(conn, 9999.0)
    insert_chat_message(conn, "user", "hi")

    reset_user(conn)

    assert not conn.in_transaction
    assert get_cash(conn) == 10000.0
    assert [w["ticker"] for w in list_watchlist(conn)] == list(DEFAULT_WATCHLIST)
    assert list_positions(conn) == []
    assert list_trades(conn) == []
    assert list_snapshots(conn) == []
    assert list_recent_chat(conn) == []


def test_reset_only_affects_user(conn):
    add_watchlist(conn, "AAPL", user_id="other")
    insert_trade(conn, "AAPL", "buy", 1, 1, user_id="other")
    reset_user(conn)
    assert len(list_trades(conn, user_id="other")) == 1
    assert len(list_watchlist(conn, user_id="other")) == 1
