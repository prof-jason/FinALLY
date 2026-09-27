"""Repository functions over the FinAlly SQLite schema.

Every function takes a connection first and a `user_id` keyword (default "default"),
and returns plain dicts. Writes are not committed here beyond the connection's
autocommit mode: wrap multi-step writes in `transaction(conn)`.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from .connection import transaction
from .schema import DEFAULT_CASH, DEFAULT_USER_ID, DEFAULT_WATCHLIST

Timestamp = datetime | str


def format_ts(dt: datetime) -> str:
    """ISO-8601 UTC with millisecond precision and a `Z` suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def utc_now() -> str:
    return format_ts(datetime.now(UTC))


def _to_ts(value: Timestamp) -> str:
    """Normalize a datetime or ISO string to the stored timestamp format."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return format_ts(value)


def _new_id() -> str:
    return str(uuid.uuid4())


# --- Cash ---------------------------------------------------------------------


def get_cash(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> float:
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"No profile for user {user_id!r}")
    return float(row["cash_balance"])


def set_cash(conn: sqlite3.Connection, amount: float, user_id: str = DEFAULT_USER_ID) -> None:
    cur = conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (float(amount), user_id)
    )
    if cur.rowcount == 0:
        raise LookupError(f"No profile for user {user_id!r}")


# --- Watchlist ----------------------------------------------------------------


def list_watchlist(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_watchlist(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Add a ticker. Returns False if it was already on the watchlist."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (_new_id(), user_id, ticker, utc_now()),
    )
    return cur.rowcount == 1


def remove_watchlist(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    """Remove a ticker. Returns False if it was not on the watchlist."""
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    )
    return cur.rowcount > 0


# --- Positions ----------------------------------------------------------------

_POSITION_COLS = "ticker, quantity, avg_cost, updated_at"


def list_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        f"SELECT {_POSITION_COLS} FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> dict | None:
    row = conn.execute(
        f"SELECT {_POSITION_COLS} FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row) if row else None


def upsert_position(
    conn: sqlite3.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Insert or overwrite the position for `ticker`. Returns the stored position."""
    now = utc_now()
    conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, ticker) DO UPDATE SET
            quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (_new_id(), user_id, ticker, float(quantity), float(avg_cost), now),
    )
    return {"ticker": ticker, "quantity": float(quantity), "avg_cost": float(avg_cost),
            "updated_at": now}


def delete_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    """Delete the position. Returns False if there was none."""
    cur = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    )
    return cur.rowcount > 0


# --- Trades -------------------------------------------------------------------


def insert_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    trade = {
        "id": _new_id(),
        "ticker": ticker,
        "side": side,
        "quantity": float(quantity),
        "price": float(price),
        "executed_at": utc_now(),
    }
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade["id"], user_id, ticker, side, trade["quantity"], trade["price"],
         trade["executed_at"]),
    )
    return trade


def list_trades(
    conn: sqlite3.Connection, limit: int = 100, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Trades newest first, at most `limit`."""
    rows = conn.execute(
        "SELECT id, ticker, side, quantity, price, executed_at FROM trades "
        "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC LIMIT ?",
        (user_id, int(limit)),
    ).fetchall()
    return [dict(r) for r in rows]


# --- Portfolio snapshots ------------------------------------------------------


def insert_snapshot(
    conn: sqlite3.Connection,
    total_value: float,
    user_id: str = DEFAULT_USER_ID,
    recorded_at: Timestamp | None = None,
) -> dict:
    """Record a portfolio value. `recorded_at` defaults to now (override is for tests)."""
    snap = {
        "id": _new_id(),
        "total_value": float(total_value),
        "recorded_at": _to_ts(recorded_at) if recorded_at is not None else utc_now(),
    }
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (snap["id"], user_id, snap["total_value"], snap["recorded_at"]),
    )
    return snap


def list_snapshots(
    conn: sqlite3.Connection, since: Timestamp | None = None, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Snapshots recorded at or after `since` (all if None), oldest first."""
    since_ts = _to_ts(since) if since is not None else ""
    rows = conn.execute(
        "SELECT total_value, recorded_at FROM portfolio_snapshots "
        "WHERE user_id = ? AND recorded_at >= ? ORDER BY recorded_at, rowid",
        (user_id, since_ts),
    ).fetchall()
    return [dict(r) for r in rows]


def prune_snapshots(
    conn: sqlite3.Connection, older_than: Timestamp, user_id: str = DEFAULT_USER_ID
) -> int:
    """Delete snapshots recorded strictly before `older_than`. Returns rows deleted."""
    cur = conn.execute(
        "DELETE FROM portfolio_snapshots WHERE user_id = ? AND recorded_at < ?",
        (user_id, _to_ts(older_than)),
    )
    return cur.rowcount


# --- Chat ---------------------------------------------------------------------


def insert_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: dict[str, Any] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    msg = {
        "id": _new_id(),
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": utc_now(),
    }
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg["id"], user_id, role, content,
         json.dumps(actions) if actions is not None else None, msg["created_at"]),
    )
    return msg


def list_recent_chat(
    conn: sqlite3.Connection, limit: int = 5, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """The last `limit` messages, returned oldest first, with `actions` decoded."""
    rows = conn.execute(
        "SELECT id, role, content, actions, created_at FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id, int(limit)),
    ).fetchall()
    messages = []
    for r in reversed(rows):
        msg = dict(r)
        msg["actions"] = json.loads(msg["actions"]) if msg["actions"] is not None else None
        messages.append(msg)
    return messages


# --- Seed / reset -------------------------------------------------------------


def seed_user(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> None:
    """Create the profile (if missing) and add the default watchlist tickers."""
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (user_id, DEFAULT_CASH, utc_now()),
    )
    for ticker in DEFAULT_WATCHLIST:
        add_watchlist(conn, ticker, user_id=user_id)


def reset_user(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> None:
    """Restore the seed state atomically (PLAN §7).

    Deletes positions, trades, snapshots, chat messages and watchlist rows, sets cash
    to 10000.0 and re-seeds the default watchlist.
    """
    with transaction(conn):
        for table in ("positions", "trades", "portfolio_snapshots", "chat_messages",
                      "watchlist"):
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        seed_user(conn, user_id=user_id)
        set_cash(conn, DEFAULT_CASH, user_id=user_id)
