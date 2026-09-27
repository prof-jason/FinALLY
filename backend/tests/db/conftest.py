"""Fixtures: every test gets its own initialized SQLite file under tmp_path."""

import pytest

from app.db import get_connection, init_db


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "data" / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    init_db()
    return path


@pytest.fixture
def conn(db_path):
    with get_connection() as c:
        yield c
