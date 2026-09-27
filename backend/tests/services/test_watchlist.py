import pytest

from app import db
from app.market import MarketDataError, UnknownTickerError
from app.services import (
    ServiceError,
    add_watchlist_ticker,
    execute_trade,
    get_watchlist,
    remove_watchlist_ticker,
    state,
    tracked_tickers,
)


def watched() -> list[str]:
    return [item["ticker"] for item in get_watchlist()]


def tracked() -> list[str]:
    with db.get_connection() as conn:
        return tracked_tickers(conn)


async def test_get_watchlist_has_prices(cache):
    items = get_watchlist()
    assert [i["ticker"] for i in items] == list(db.DEFAULT_WATCHLIST)
    aapl = items[0]
    assert set(aapl) == {
        "ticker",
        "price",
        "previous_price",
        "change",
        "change_percent",
        "direction",
        "added_at",
    }
    assert aapl["price"] == cache.get_price("AAPL")
    assert aapl["direction"] in ("up", "down", "flat")


async def test_watchlist_price_fields_null_without_cache(cache):
    cache.remove("AAPL")
    aapl = get_watchlist()[0]
    assert aapl["price"] is None and aapl["direction"] is None


async def test_add_ticker_tracks_and_prices(cache, source):
    item = await add_watchlist_ticker(" pypl ")
    assert item["ticker"] == "PYPL"
    assert item["price"] is not None
    assert item["added_at"]
    assert watched()[-1] == "PYPL"
    assert "PYPL" in source.get_tickers()


async def test_add_existing_is_noop(cache):
    await add_watchlist_ticker("AAPL")
    assert watched().count("AAPL") == 1


@pytest.mark.parametrize("ticker", ["", "123", "TOOLONG", "BRK.B"])
async def test_add_invalid_rejected(cache, ticker):
    with pytest.raises(ServiceError) as err:
        await add_watchlist_ticker(ticker)
    assert err.value.status_code == 400


class RejectingSource:
    def __init__(self, exc):
        self.exc = exc

    async def add_ticker(self, ticker):
        raise self.exc


@pytest.mark.parametrize(
    ("exc", "status"), [(UnknownTickerError("XYZ"), 404), (MarketDataError("down"), 503)]
)
async def test_add_rejected_by_source_writes_nothing(cache, exc, status):
    state.configure(cache, RejectingSource(exc))
    with pytest.raises(ServiceError) as err:
        await add_watchlist_ticker("XYZ")
    assert err.value.status_code == status
    if status == 404:
        assert err.value.message == "Unknown ticker: XYZ"
    assert "XYZ" not in watched()


async def test_remove_untracks_when_not_held(cache, source):
    await remove_watchlist_ticker("nflx")
    assert "NFLX" not in watched()
    assert "NFLX" not in source.get_tickers()
    assert "NFLX" not in cache


async def test_remove_unknown_is_404(cache):
    with pytest.raises(ServiceError) as err:
        await remove_watchlist_ticker("PYPL")
    assert err.value.status_code == 404


async def test_tracked_is_watchlist_union_positions(cache):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 1)
    await remove_watchlist_ticker("AAPL")
    assert "AAPL" not in watched()
    assert tracked() == [*db.DEFAULT_WATCHLIST[1:], "AAPL"]


async def test_removing_watched_and_held_keeps_tracking(cache, source):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 2)
    await remove_watchlist_ticker("AAPL")
    assert "AAPL" in source.get_tickers()
    assert "AAPL" in cache

    # Partial sell: still held, still tracked
    await execute_trade("AAPL", "sell", 1)
    assert "AAPL" in source.get_tickers()

    # Fully sold and not watched: tracking stops
    await execute_trade("AAPL", "sell", 1)
    assert "AAPL" not in source.get_tickers()
    assert "AAPL" not in cache


async def test_selling_watched_ticker_keeps_tracking(cache, source):
    cache.update("AAPL", 100.0)
    await execute_trade("AAPL", "buy", 1)
    await execute_trade("AAPL", "sell", 1)
    assert "AAPL" in source.get_tickers()


async def test_buy_unwatched_ticker_with_cached_price(cache, source):
    await add_watchlist_ticker("PYPL")
    await remove_watchlist_ticker("PYPL")
    assert "PYPL" not in cache
    with pytest.raises(ServiceError, match="No price available for PYPL"):
        await execute_trade("PYPL", "buy", 1)
