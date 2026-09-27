"""Lazy database initialization: create tables and seed defaults."""

from __future__ import annotations

from pathlib import Path

from .connection import get_connection, transaction
from .repository import seed_user
from .schema import DEFAULT_USER_ID, SCHEMA_SQL


def init_db(db_path: str | Path | None = None) -> None:
    """Create tables if missing and seed the default user if absent. Idempotent."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        with transaction(conn):
            row = conn.execute(
                "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
            ).fetchone()
            if row is None:
                seed_user(conn)
