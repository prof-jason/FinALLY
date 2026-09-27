"""Chat flow: LLM call, auto-execution, history, persistence (fakes only, no network)."""

import json

import pytest

from app.llm import client
from app.llm.client import MODEL, LLMUnavailableError
from app.llm.service import handle_chat


def _reply(message="ok", trades=(), changes=()):
    return json.dumps(
        {"message": message, "trades": list(trades), "watchlist_changes": list(changes)}
    )


async def test_calls_free_model_with_structured_output(fake_services, fake_db, llm_reply):
    await handle_chat("hello")
    call = llm_reply.calls[0]
    assert call["model"] == MODEL == "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    assert call["response_format"] is client.ChatResponse
    assert call["reasoning_effort"] == "low"
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["system", "system", "user"]
    assert "$10,000.00" in call["messages"][1]["content"]


async def test_trade_executed_and_returned(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply(
        "Placing an order for 10 AAPL.", trades=[{"ticker": "aapl", "side": "buy", "quantity": 10}]
    )
    result = await handle_chat("buy 10 apple")
    assert result == {
        "message": "Placing an order for 10 AAPL.",
        "actions": {
            "trades": [
                {
                    "ticker": "AAPL",
                    "side": "buy",
                    "quantity": 10.0,
                    "status": "executed",
                    "price": 190.0,
                }
            ],
            "watchlist_changes": [],
        },
    }
    assert fake_services.cash == pytest.approx(10000 - 1900)


async def test_trade_validation_failures_reported(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply(
        trades=[
            {"ticker": "TSLA", "side": "buy", "quantity": 500},  # insufficient cash
            {"ticker": "MSFT", "side": "sell", "quantity": 1},  # nothing held
            {"ticker": "ZZZZ", "side": "buy", "quantity": 1},  # no price
            {"ticker": "AAPL", "side": "buy", "quantity": 0},  # qty <= 0
        ]
    )
    result = await handle_chat("go")
    trades = result["actions"]["trades"]
    assert [t["status"] for t in trades] == ["failed"] * 4
    assert [t["error"] for t in trades] == [
        "Insufficient cash",
        "Insufficient shares",
        "No price available for ZZZZ",
        "Quantity must be greater than 0",
    ]
    assert all("price" not in t for t in trades)
    assert fake_services.cash == 10000.0


async def test_partial_failure_does_not_block_others(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply(
        trades=[
            {"ticker": "AAPL", "side": "buy", "quantity": 1},
            {"ticker": "TSLA", "side": "buy", "quantity": 500},
            {"ticker": "MSFT", "side": "buy", "quantity": 2},
        ],
        changes=[{"ticker": "NOPE", "action": "remove"}, {"ticker": "PYPL", "action": "add"}],
    )
    result = await handle_chat("go")
    assert [t["status"] for t in result["actions"]["trades"]] == ["executed", "failed", "executed"]
    assert [c["status"] for c in result["actions"]["watchlist_changes"]] == ["failed", "executed"]
    assert set(fake_services.positions) == {"AAPL", "MSFT"}
    assert "PYPL" in fake_services.watchlist


async def test_watchlist_changes_run_before_trades(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply(
        trades=[{"ticker": "AAPL", "side": "buy", "quantity": 1}],
        changes=[{"ticker": "PYPL", "action": "add"}, {"ticker": "TSLA", "action": "remove"}],
    )
    await handle_chat("go")
    assert [c[0] for c in fake_services.calls] == ["add", "remove", "trade"]


async def test_sell_all_then_buy_in_order(fake_services, fake_db, llm_reply):
    fake_services.execute_trade("AAPL", "buy", 2)
    fake_services.calls.clear()
    llm_reply.content = _reply(
        trades=[
            {"ticker": "AAPL", "side": "sell", "quantity": 2},
            {"ticker": "AAPL", "side": "sell", "quantity": 1},
        ]
    )
    result = await handle_chat("sell")
    assert [t["status"] for t in result["actions"]["trades"]] == ["executed", "failed"]
    assert "AAPL" not in fake_services.positions


async def test_messages_and_actions_persisted(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply("Adding PYPL.", changes=[{"ticker": "PYPL", "action": "add"}])
    result = await handle_chat("watch paypal")
    assert [m["role"] for m in fake_db.messages] == ["user", "assistant"]
    assert fake_db.messages[0] == {"role": "user", "content": "watch paypal", "actions": None}
    assert fake_db.messages[1]["content"] == "Adding PYPL."
    assert fake_db.messages[1]["actions"] == result["actions"]


async def test_only_last_five_messages_sent(fake_services, fake_db, llm_reply):
    for i in range(8):
        fake_db.messages.append(
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}", "actions": None}
        )
    await handle_chat("new")
    assert fake_db.list_limits == [5]
    sent = llm_reply.calls[0]["messages"]
    assert [m["content"] for m in sent[2:]] == ["m3", "m4", "m5", "m6", "m7", "new"]


async def test_history_includes_previous_action_results(fake_services, fake_db, llm_reply):
    llm_reply.content = _reply(trades=[{"ticker": "TSLA", "side": "buy", "quantity": 500}])
    await handle_chat("buy lots of tesla")
    llm_reply.content = _reply("It failed.")
    await handle_chat("what happened?")
    sent = llm_reply.calls[1]["messages"]
    assert sent[2] == {"role": "user", "content": "buy lots of tesla"}
    assert sent[3]["role"] == "assistant" and "Insufficient cash" in sent[3]["content"]


async def test_malformed_reply_still_answers(fake_services, fake_db, llm_reply):
    llm_reply.content = "Sorry, plain text only."
    result = await handle_chat("hi")
    assert result == {
        "message": "Sorry, plain text only.",
        "actions": {"trades": [], "watchlist_changes": []},
    }


async def test_llm_error_raises_unavailable_and_persists_nothing(fake_services, fake_db, llm_reply):
    llm_reply.error = RuntimeError("429 rate limited")
    with pytest.raises(LLMUnavailableError):
        await handle_chat("hi")
    assert fake_db.messages == []


async def test_empty_reply_raises_unavailable(fake_services, fake_db, llm_reply):
    llm_reply.content = ""
    with pytest.raises(LLMUnavailableError):
        await handle_chat("hi")


async def test_mock_mode_skips_llm_and_executes(fake_services, fake_db, llm_reply, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    result = await handle_chat("buy 2 AAPL and add PYPL")
    assert llm_reply.calls == []
    assert result["actions"]["trades"][0]["status"] == "executed"
    assert result["actions"]["watchlist_changes"][0] == {
        "ticker": "PYPL",
        "action": "add",
        "status": "executed",
    }
    assert len(fake_db.messages) == 2


async def test_mock_mode_default_message(fake_services, fake_db, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    result = await handle_chat("how am I doing?")
    assert result == {
        "message": "Mock response: I can help you analyze your portfolio.",
        "actions": {"trades": [], "watchlist_changes": []},
    }
