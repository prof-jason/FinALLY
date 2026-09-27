"""Connection handling, schema creation, lazy init and seeding."""

import sqlite3

import pytest

from app.db import (
    DEFAULT_DB_PATH,
    DEFAULT_WATCHLIST,
    get_cash,
    get_connection,
    get_db_path,
    init_db,
    list_watchlist,
    set_cash,
    transaction,
)

TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def test_db_path_default(monkeypatch):
    monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
    assert get_db_path() == DEFAULT_DB_PATH
    assert DEFAULT_DB_PATH.parent.name == "db"
    assert (DEFAULT_DB_PATH.parent.parent / "backend").is_dir()


def test_db_path_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "x.db"))
    assert get_db_path() == tmp_path / "x.db"


def test_init_creates_parent_dir_and_tables(db_path):
    assert db_path.exists()
    with get_connection() as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert TABLES <= names


def test_connection_settings(conn):
    assert conn.row_factory is sqlite3.Row
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_all_tables_have_user_id(conn):
    for table in TABLES - {"users_profile"}:
        cols = {r["name"]: r for r in conn.execute(f"PRAGMA table_info({table})")}
        assert "user_id" in cols
        assert cols["user_id"]["dflt_value"] == "'default'"


def test_seed_data(conn):
    assert get_cash(conn) == 10000.0
    assert [w["ticker"] for w in list_watchlist(conn)] == list(DEFAULT_WATCHLIST)
    assert len(DEFAULT_WATCHLIST) == 10


def test_init_is_idempotent_and_preserves_data(db_path):
    with get_connection() as conn:
        set_cash(conn, 123.0)
    init_db()
    init_db()
    with get_connection() as conn:
        assert get_cash(conn) == 123.0
        assert len(list_watchlist(conn)) == 10
        assert conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()[0] == 1


def test_init_explicit_path(tmp_path):
    path = tmp_path / "nested" / "dir" / "other.db"
    init_db(path)
    with get_connection(path) as conn:
        assert get_cash(conn) == 10000.0


def test_transaction_commits(db_path):
    with transaction() as conn:
        set_cash(conn, 1.0)
    with get_connection() as conn:
        assert get_cash(conn) == 1.0


def test_transaction_rolls_back_on_error(db_path):
    with pytest.raises(RuntimeError):
        with transaction() as conn:
            set_cash(conn, 1.0)
            raise RuntimeError("boom")
    with get_connection() as conn:
        assert get_cash(conn) == 10000.0


def test_transaction_on_existing_conn_and_nesting(conn):
    with pytest.raises(RuntimeError):
        with transaction(conn):
            set_cash(conn, 5.0)
            with transaction(conn):  # joins the outer transaction
                set_cash(conn, 6.0)
            raise RuntimeError("boom")
    assert not conn.in_transaction
    assert get_cash(conn) == 10000.0


def test_autocommit_visible_to_other_connections(conn):
    set_cash(conn, 42.0)
    with get_connection() as other:
        assert get_cash(other) == 42.0
