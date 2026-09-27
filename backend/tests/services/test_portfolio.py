from datetime import UTC, datetime, timedelta

import pytest

from app import db
from app.services import (
    ServiceError,
    execute_trade,
    get_history,
    get_portfolio,
    get_trades,
    record_snapshot,
    reset_portfolio,
)


def snapshot_count() -> int:
    with db.get_connection() as conn:
        return len(db.list_snapshots(conn))


async def test_initial_portfolio(cache):
    p = get_portfolio()
    assert p == {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "positions": [],
    }


async def test_buy_debits_cash_and_opens_position(cache):
    cache.update("AAPL", 100.0)
    result = await execute_trade("aapl", "buy", 10)

    trade = result["trade"]
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10
    assert trade["price"] == 100.0
    assert trade["id"] and trade["executed_at"].endswith("Z")

    p = result["portfolio"]
    assert p["cash_balance"] == 9000.0
    assert p["total_value"] == 10000.0
    [pos] = p["positions"]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 100.0
    assert pos["market_value"] == 1000.0
    assert get_portfolio() == p


async def test_buy_averages_cost(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 10)
    cache.update("AAPL", 130.0)
    result = await execute_trade("AAPL", "buy", 5)
    [pos] = result["portfolio"]["positions"]
    assert pos["quantity"] == 15
    assert pos["avg_cost"] == pytest.approx(110.0)


async def test_unrealized_pnl_follows_cache(cache):
    cache.update("NVDA", 200.0)
    await execute_trade("NVDA", "buy", 4)
    cache.update("NVDA", 250.0)
    p = get_portfolio()
    [pos] = p["positions"]
    assert pos["current_price"] == 250.0
    assert pos["unrealized_pnl"] == 200.0
    assert pos["unrealized_pnl_percent"] == 25.0
    assert p["total_unrealized_pnl"] == 200.0
    assert p["total_value"] == 10200.0


async def test_current_price_falls_back_to_avg_cost(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 1)
    cache.remove("AAPL")
    [pos] = get_portfolio()["positions"]
    assert pos["current_price"] == 100.0
    assert pos["unrealized_pnl"] == 0.0


async def test_fractional_quantities(cache):
    cache.update("AAPL", 200.0)
    await execute_trade("AAPL", "buy", 2.5)
    result = await execute_trade("AAPL", "sell", 1.25)
    [pos] = result["portfolio"]["positions"]
    assert pos["quantity"] == pytest.approx(1.25)
    assert result["portfolio"]["cash_balance"] == 9750.0


async def test_sell_at_loss_keeps_avg_cost(cache):
    cache.update("TSLA", 300.0)
    await execute_trade("TSLA", "buy", 10)
    cache.update("TSLA", 250.0)
    result = await execute_trade("TSLA", "sell", 4)
    p = result["portfolio"]
    [pos] = p["positions"]
    assert pos["avg_cost"] == 300.0
    assert pos["quantity"] == 6
    assert p["cash_balance"] == 10000 - 3000 + 1000
    assert pos["unrealized_pnl"] == -300.0


async def test_sell_to_exactly_zero_deletes_position(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 0.1)
    await execute_trade("AAPL", "buy", 0.2)
    # 0.1 + 0.2 != 0.3 in floating point; the 1e-9 rule absorbs it
    result = await execute_trade("AAPL", "sell", 0.3)
    assert result["portfolio"]["positions"] == []
    with db.get_connection() as conn:
        assert db.get_position(conn, "AAPL") is None


async def test_sell_more_than_owned_rejected(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 1)
    with pytest.raises(ServiceError) as err:
        await execute_trade("AAPL", "sell", 2)
    assert err.value.status_code == 400
    assert err.value.message == "Insufficient shares"
    assert get_portfolio()["positions"][0]["quantity"] == 1


async def test_sell_unheld_rejected(cache):
    with pytest.raises(ServiceError, match="Insufficient shares"):
        await execute_trade("AAPL", "sell", 1)


async def test_insufficient_cash_rejected_and_nothing_written(cache):
    cache.update("AAPL", 100.0)
    with pytest.raises(ServiceError) as err:
        await execute_trade("AAPL", "buy", 101)
    assert err.value.status_code == 400
    assert err.value.message == "Insufficient cash"
    assert get_portfolio()["cash_balance"] == 10000.0
    assert get_trades() == []
    assert snapshot_count() == 0


async def test_buy_exactly_all_cash(cache):
    cache.update("AAPL", 100.0)
    result = await execute_trade("AAPL", "buy", 100)
    assert result["portfolio"]["cash_balance"] == 0.0


@pytest.mark.parametrize("qty", [0, -1, -0.5, float("nan"), float("inf"), "abc", None, True])
async def test_bad_quantity_rejected(cache, qty):
    cache.update("AAPL", 100.0)
    with pytest.raises(ServiceError) as err:
        await execute_trade("AAPL", "buy", qty)
    assert err.value.status_code == 400


async def test_numeric_string_quantity_accepted(cache):
    cache.update("AAPL", 100.0)
    result = await execute_trade("AAPL", "buy", "1.5")
    assert result["trade"]["quantity"] == 1.5


async def test_bad_side_rejected(cache):
    with pytest.raises(ServiceError, match="Side"):
        await execute_trade("AAPL", "short", 1)


@pytest.mark.parametrize("ticker", ["", "TOOLONG", "AB1", "A-B", "  "])
async def test_bad_ticker_rejected(cache, ticker):
    with pytest.raises(ServiceError) as err:
        await execute_trade(ticker, "buy", 1)
    assert err.value.status_code == 400


async def test_no_cached_price_rejected(cache):
    with pytest.raises(ServiceError) as err:
        await execute_trade("ZZZZ", "buy", 1)
    assert err.value.status_code == 400
    assert err.value.message == "No price available for ZZZZ"


async def test_trade_records_trade_and_snapshot(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 1)
    await execute_trade("AAPL", "sell", 1)
    trades = get_trades()
    assert [t["side"] for t in trades] == ["sell", "buy"]  # newest first
    assert snapshot_count() == 2
    assert get_trades(limit=1)[0]["side"] == "sell"


async def test_get_trades_limit_validation(cache):
    with pytest.raises(ServiceError):
        get_trades(0)


async def test_record_snapshot_prunes_older_than_10_days(cache):
    old = datetime.now(UTC) - timedelta(days=11)
    recent = datetime.now(UTC) - timedelta(days=9)
    with db.get_connection() as conn:
        for ts in (old, recent):
            conn.execute(
                "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)"
                " VALUES (?, 'default', 1.0, ?)",
                (ts.isoformat(), db.format_ts(ts)),
            )
    record_snapshot()
    with db.get_connection() as conn:
        snaps = db.list_snapshots(conn)
    assert len(snaps) == 2
    assert snaps[0]["recorded_at"] == db.format_ts(recent)
    assert snaps[1]["total_value"] == 10000.0

    history = get_history()
    assert [h["total_value"] for h in history] == [1.0, 10000.0]
    assert set(history[0]) == {"total_value", "recorded_at"}


async def test_reset_restores_seed_state(cache, source):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 5)
    with db.get_connection() as conn:
        db.remove_watchlist(conn, "GOOGL")
        db.add_watchlist(conn, "PYPL")
        db.insert_chat_message(conn, "user", "hi", None)
    await source.add_ticker("PYPL")

    p = await reset_portfolio()
    assert p == {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "positions": [],
    }
    assert get_trades() == []
    assert get_history() == []
    with db.get_connection() as conn:
        assert [r["ticker"] for r in db.list_watchlist(conn)] == list(db.DEFAULT_WATCHLIST)
        assert db.list_recent_chat(conn) == []
    assert sorted(source.get_tickers()) == sorted(db.DEFAULT_WATCHLIST)
    assert "PYPL" not in cache
    assert all(t in cache for t in db.DEFAULT_WATCHLIST)
