import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A running app (lifespan included) on a fresh DB with the simulator."""
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.setenv("FINALLY_STATIC_DIR", str(tmp_path / "no-static"))
    monkeypatch.setenv("LLM_MOCK", "true")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def cache():
    from app.services import state

    return state.get_price_cache()
