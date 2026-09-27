"""SQLite connection handling."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# backend/app/db/connection.py -> repo root is three levels above backend/app/db
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _REPO_ROOT / "db" / "finally.db"


def get_db_path() -> Path:
    """Resolve the DB path from FINALLY_DB_PATH (read on every call, so tests can override)."""
    env = os.environ.get("FINALLY_DB_PATH")
    return Path(env) if env else DEFAULT_DB_PATH


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a new connection in autocommit mode with WAL and Row factory.

    Autocommit means each repository call commits on its own; use `transaction()`
    to group several writes atomically.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a fresh connection and close it afterwards."""
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(
    conn: sqlite3.Connection | None = None, db_path: str | Path | None = None
) -> Iterator[sqlite3.Connection]:
    """Run a block atomically: BEGIN IMMEDIATE, then COMMIT, or ROLLBACK on error.

    With no `conn`, opens (and closes) its own connection. With `conn`, uses it;
    if `conn` is already inside a transaction, the block joins it (no nesting).
    """
    if conn is None:
        with get_connection(db_path) as own:
            with transaction(own) as c:
                yield c
        return

    if conn.in_transaction:
        yield conn
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
