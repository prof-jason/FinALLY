"""System prompt, portfolio context and message assembly."""

from app.llm.prompt import SYSTEM_PROMPT, build_messages, build_portfolio_context


def _portfolio():
    return {
        "cash_balance": 5000.0,
        "total_value": 6000.0,
        "total_unrealized_pnl": 50.0,
        "positions": [
            {
                "ticker": "AAPL",
                "quantity": 5,
                "avg_cost": 190.0,
                "current_price": 200.0,
                "market_value": 1000.0,
                "unrealized_pnl": 50.0,
                "unrealized_pnl_percent": 5.26,
            }
        ],
    }


def test_system_prompt_covers_guidance():
    text = SYSTEM_PROMPT.lower()
    assert "finally" in text and "json" in text
    assert "short sell" in text and "margin" in text
    assert "placing an order" in text


def test_context_includes_cash_positions_watchlist_total():
    ctx = build_portfolio_context(
        _portfolio(),
        [
            {"ticker": "TSLA", "price": 251.5, "change_percent": -0.4},
            {"ticker": "NEW", "price": None, "change_percent": None},
        ],
    )
    assert "$5,000.00" in ctx and "$6,000.00" in ctx
    assert "AAPL: 5 shares" in ctx and "16.7% of portfolio" in ctx and "+5.26%" in ctx
    assert "TSLA: $251.50" in ctx and "NEW: n/a" in ctx


def test_context_empty_portfolio():
    ctx = build_portfolio_context(
        {
            "cash_balance": 10000.0,
            "total_value": 10000.0,
            "total_unrealized_pnl": 0.0,
            "positions": [],
        },
        [],
    )
    assert "Positions: none" in ctx and "Watchlist: empty" in ctx


def test_build_messages_order_and_action_results():
    history = [
        {"role": "user", "content": "buy lots", "actions": None},
        {
            "role": "assistant",
            "content": "Placing an order.",
            "actions": {
                "trades": [{"ticker": "TSLA", "status": "failed", "error": "Insufficient cash"}],
                "watchlist_changes": [],
            },
        },
    ]
    msgs = build_messages("CTX", history, "why did that fail?")
    assert [m["role"] for m in msgs] == ["system", "system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "CTX"
    assert "Insufficient cash" in msgs[3]["content"]
    assert msgs[-1]["content"] == "why did that fail?"


def test_empty_actions_not_appended():
    history = [
        {"role": "assistant", "content": "Hi", "actions": {"trades": [], "watchlist_changes": []}}
    ]
    assert build_messages("CTX", history, "x")[2]["content"] == "Hi"
