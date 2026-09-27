"""Chat flow against the real app.db and app.services (LLM still monkeypatched)."""

import json

import pytest

from app import db
from app.llm.service import handle_chat
from app.market import PriceCache, SimulatorDataSource
from app.services import state


@pytest.fixture
async def real_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "finally.db"))
    db.init_db()
    cache = PriceCache()
    source = SimulatorDataSource(cache, update_interval=3600, seed=7)
    state.configure(cache, source)
    await source.start(list(db.DEFAULT_WATCHLIST))
    yield cache, source
    await source.stop()
    state.clear()


async def test_actions_execute_and_persist(real_backend, llm_reply):
    cache, source = real_backend
    llm_reply.content = json.dumps(
        {
            "message": "Placing orders.",
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 2},
                {"ticker": "TSLA", "side": "buy", "quantity": 100000},
                {"ticker": "PYPL", "side": "buy", "quantity": 1},
            ],
            "watchlist_changes": [
                {"ticker": "PYPL", "action": "add"},
                {"ticker": "NFLX", "action": "remove"},
                {"ticker": "bad-1", "action": "add"},
            ],
        }
    )
    result = await handle_chat("do things")

    changes = result["actions"]["watchlist_changes"]
    assert [c["status"] for c in changes] == ["executed", "executed", "failed"]
    trades = result["actions"]["trades"]
    assert [t["status"] for t in trades] == ["executed", "failed", "executed"]
    assert trades[0]["price"] == cache.get_price("AAPL")
    assert trades[1]["error"] == "Insufficient cash"

    with db.get_connection() as conn:
        held = {p["ticker"] for p in db.list_positions(conn)}
        watched = {w["ticker"] for w in db.list_watchlist(conn)}
        chat = db.list_recent_chat(conn)
    assert held == {"AAPL", "PYPL"}
    assert "PYPL" in watched and "NFLX" not in watched
    assert [m["role"] for m in chat] == ["user", "assistant"]
    assert chat[1]["actions"] == result["actions"]

    # The LLM context was built from real services.
    context = llm_reply.calls[0]["messages"][1]["content"]
    assert "$10,000.00" in context and "AAPL:" in context


async def test_history_capped_at_five(real_backend, llm_reply):
    for i in range(4):
        await handle_chat(f"turn {i}")
    await handle_chat("latest")
    sent = llm_reply.calls[-1]["messages"]
    history = sent[2:-1]
    assert len(history) == 5
    assert history[0] == {"role": "assistant", "content": "ok"}
    assert history[-1]["role"] == "assistant"
    assert sent[-1] == {"role": "user", "content": "latest"}


async def test_mock_mode_end_to_end(real_backend, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    result = await handle_chat("buy 1 AAPL")
    assert result["actions"]["trades"][0]["status"] == "executed"
    result = await handle_chat("sell 5 AAPL")
    assert result["actions"]["trades"][0] == {
        "ticker": "AAPL",
        "side": "sell",
        "quantity": 5.0,
        "status": "failed",
        "error": "Insufficient shares",
    }
