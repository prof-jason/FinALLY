"""SQLite persistence layer for FinAlly.

Public API:
    init_db            - Create tables and seed defaults (idempotent; call at startup)
    get_connection     - Context manager yielding an autocommit connection (Row factory, WAL)
    transaction        - Context manager: BEGIN IMMEDIATE ... COMMIT / ROLLBACK
    get_db_path        - Resolved DB path (FINALLY_DB_PATH or <repo>/db/finally.db)
    Repository functions (conn first, `user_id="default"` kwarg, plain dicts):
        get_cash, set_cash,
        list_watchlist, add_watchlist, remove_watchlist,
        list_positions, get_position, upsert_position, delete_position,
        insert_trade, list_trades,
        insert_snapshot, list_snapshots, prune_snapshots,
        insert_chat_message, list_recent_chat,
        reset_user
"""

from .connection import DEFAULT_DB_PATH, connect, get_connection, get_db_path, transaction
from .init import init_db
from .repository import (
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
from .schema import DEFAULT_CASH, DEFAULT_USER_ID, DEFAULT_WATCHLIST

__all__ = [
    "DEFAULT_CASH",
    "DEFAULT_DB_PATH",
    "DEFAULT_USER_ID",
    "DEFAULT_WATCHLIST",
    "add_watchlist",
    "connect",
    "delete_position",
    "format_ts",
    "get_cash",
    "get_connection",
    "get_db_path",
    "get_position",
    "init_db",
    "insert_chat_message",
    "insert_snapshot",
    "insert_trade",
    "list_positions",
    "list_recent_chat",
    "list_snapshots",
    "list_trades",
    "list_watchlist",
    "prune_snapshots",
    "remove_watchlist",
    "reset_user",
    "set_cash",
    "transaction",
    "upsert_position",
    "utc_now",
]
