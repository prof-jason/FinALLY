"""POST /api/chat over HTTP."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.llm import create_chat_router


@pytest.fixture
def http(fake_services, fake_db):
    app = FastAPI()
    app.include_router(create_chat_router())
    return TestClient(app)


def test_chat_success_shape(http, llm_reply):
    llm_reply.content = (
        '{"message": "Placing an order for 1 AAPL.", "trades": '
        '[{"ticker": "AAPL", "side": "buy", "quantity": 1}], '
        '"watchlist_changes": []}'
    )
    r = http.post("/api/chat", json={"message": "buy one apple"})
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "Placing an order for 1 AAPL."
    assert body["actions"]["trades"][0]["status"] == "executed"
    assert body["actions"]["watchlist_changes"] == []


def test_chat_llm_failure_returns_503(http, llm_reply):
    llm_reply.error = RuntimeError("rate limit")
    r = http.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503
    assert r.json() == {
        "error": "The AI assistant is unavailable right now, please try again shortly."
    }


def test_chat_blank_message_rejected(http, llm_reply):
    r = http.post("/api/chat", json={"message": "   "})
    assert r.status_code == 400
    assert "error" in r.json()
    assert llm_reply.calls == []


def test_chat_mock_mode(http, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    r = http.post("/api/chat", json={"message": "sell 1 AAPL"})
    assert r.status_code == 200
    trade = r.json()["actions"]["trades"][0]
    assert trade["status"] == "failed" and trade["error"] == "Insufficient shares"
