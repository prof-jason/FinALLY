import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from massive.rest.models import SnapshotMarketType, TickerSnapshot

from app.market.cache import PriceCache
from app.market.massive_client import (
    MassiveDataSource,
    extract_price,
    extract_timestamp,
    to_unix_seconds,
)
from app.market.tickers import MarketDataError, UnknownTickerError

TS_NS = 1_707_580_800_123_000_000  # 2024-02-10T16:00:00.123Z in nanoseconds
TS_S = 1_707_580_800.123


def snapshot(ticker, price=None, *, ts=TS_NS, day_close=None, prev_close=None, min_close=None):
    """Build a real massive TickerSnapshot from API-shaped JSON."""
    d = {"ticker": ticker, "updated": ts}
    if price is not None:
        d["lastTrade"] = {"T": ticker, "p": price, "s": 100, "t": ts, "x": 4}
    if day_close is not None:
        d["day"] = {"o": 1, "h": 1, "l": 1, "c": day_close, "v": 1}
    if prev_close is not None:
        d["prevDay"] = {"o": 1, "h": 1, "l": 1, "c": prev_close, "v": 1}
    if min_close is not None:
        d["min"] = {"o": 1, "h": 1, "l": 1, "c": min_close, "v": 1, "t": ts}
    return TickerSnapshot.from_dict(d)


class FakeClient:
    """Stands in for massive.RESTClient.get_snapshot_all."""

    def __init__(self, snapshots=None, error=None):
        self.snapshots = snapshots or {}
        self.error = error
        self.calls = []

    def get_snapshot_all(self, market_type, tickers):
        self.calls.append((market_type, list(tickers)))
        if self.error:
            raise self.error
        return [self.snapshots[t] for t in tickers if t in self.snapshots]


def make_source(client, interval=60.0):
    cache = PriceCache()
    return MassiveDataSource("test-key", cache, poll_interval=interval, client=client), cache


# --- Parsing helpers ---


def test_extract_price_prefers_last_trade():
    snap = snapshot("AAPL", 190.5, day_close=189.0, prev_close=188.0, min_close=190.0)
    assert extract_price(snap) == 190.5


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"min_close": 190.0, "day_close": 189.0, "prev_close": 188.0}, 190.0),
        ({"day_close": 189.0, "prev_close": 188.0}, 189.0),
        ({"prev_close": 188.0}, 188.0),
        ({"day_close": 0, "prev_close": 188.0}, 188.0),  # zeroed day bar pre-market
        ({}, None),
    ],
)
def test_extract_price_fallbacks(kwargs, expected):
    assert extract_price(snapshot("AAPL", **kwargs)) == expected


def test_extract_price_handles_none_and_garbage():
    assert extract_price(None) is None
    assert extract_price(SimpleNamespace(last_trade=SimpleNamespace(price="abc"))) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (TS_NS, TS_S),
        (1_707_580_800_123_000, TS_S),
        (1_707_580_800_123, TS_S),
        (1_707_580_800, 1_707_580_800.0),
        (None, None),
        (0, None),
        (-5, None),
        ("x", None),
    ],
)
def test_to_unix_seconds(raw, expected):
    result = to_unix_seconds(raw)
    assert result == (pytest.approx(expected) if expected is not None else None)


def test_extract_timestamp_from_last_trade():
    assert extract_timestamp(snapshot("AAPL", 1.0)) == pytest.approx(TS_S)


def test_extract_timestamp_falls_back_to_updated_then_now(monkeypatch):
    snap = snapshot("AAPL", prev_close=1.0)  # no last trade, has `updated`
    assert extract_timestamp(snap) == pytest.approx(TS_S)
    monkeypatch.setattr("time.time", lambda: 42.0)
    assert extract_timestamp(SimpleNamespace()) == 42.0


# --- Polling ---


async def test_start_polls_immediately():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5), "GOOGL": snapshot("GOOGL", 175.25)})
    source, cache = make_source(client)
    await source.start(["AAPL", "GOOGL"])
    try:
        assert client.calls == [(SnapshotMarketType.STOCKS, ["AAPL", "GOOGL"])]
        assert cache.get_price("AAPL") == 190.5
        assert cache.get_price("GOOGL") == 175.25
        assert cache.get("AAPL").timestamp == pytest.approx(TS_S)
    finally:
        await source.stop()


async def test_start_dedupes_tickers():
    source, _ = make_source(FakeClient())
    await source.start(["AAPL", "AAPL", "MSFT"])
    await source.stop()
    assert source.get_tickers() == ["AAPL", "MSFT"]


async def test_start_creates_rest_client_with_api_key():
    cache = PriceCache()
    source = MassiveDataSource("secret", cache, poll_interval=60)
    with patch("app.market.massive_client.RESTClient") as rest_client:
        rest_client.return_value = FakeClient()
        await source.start(["AAPL"])
        await source.stop()
    rest_client.assert_called_once_with(api_key="secret")


async def test_poll_loop_repeats_on_interval():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5)})
    source, _ = make_source(client, interval=0.02)
    await source.start(["AAPL"])
    await asyncio.sleep(0.1)
    await source.stop()
    assert len(client.calls) >= 3


async def test_stop_halts_polling_and_is_idempotent():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5)})
    source, _ = make_source(client, interval=0.01)
    await source.start(["AAPL"])
    await source.stop()
    n = len(client.calls)
    await asyncio.sleep(0.05)
    assert len(client.calls) == n
    await source.stop()


async def test_poll_skips_snapshots_without_price():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5), "BAD": snapshot("BAD")})
    source, cache = make_source(client)
    source._tickers = ["AAPL", "BAD"]
    await source._poll_once()
    assert cache.get_price("AAPL") == 190.5
    assert cache.get_price("BAD") is None


async def test_poll_tolerates_malformed_objects():
    bad = SimpleNamespace(ticker="AAPL", last_trade=None)
    client = FakeClient({"AAPL": bad})
    source, cache = make_source(client)
    source._tickers = ["AAPL"]
    await source._poll_once()
    assert cache.get_price("AAPL") is None


async def test_poll_api_error_does_not_raise_and_keeps_last_prices():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5)})
    source, cache = make_source(client)
    source._tickers = ["AAPL"]
    await source._poll_once()
    client.error = RuntimeError("429 Too Many Requests")
    await source._poll_once()
    assert cache.get_price("AAPL") == 190.5


async def test_poll_loop_survives_errors():
    client = FakeClient(error=RuntimeError("network down"))
    source, _ = make_source(client, interval=0.01)
    await source.start(["AAPL"])
    await asyncio.sleep(0.05)
    assert source._task is not None and not source._task.done()
    await source.stop()
    assert len(client.calls) > 1


async def test_poll_with_no_tickers_skips_api_call():
    client = FakeClient()
    source, _ = make_source(client)
    await source.start([])
    await source.stop()
    assert client.calls == []


async def test_poll_ignores_tickers_removed_mid_flight():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5), "TSLA": snapshot("TSLA", 250.0)})
    source, cache = make_source(client)
    source._tickers = ["AAPL", "TSLA"]
    real_fetch = source._fetch_snapshots

    def fetch_then_remove(tickers):
        result = real_fetch(tickers)
        source._tickers.remove("TSLA")
        return result

    source._fetch_snapshots = fetch_then_remove
    await source._poll_once()
    assert cache.get_price("AAPL") == 190.5
    assert cache.get("TSLA") is None


async def test_price_direction_across_polls():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.0)})
    source, cache = make_source(client)
    source._tickers = ["AAPL"]
    await source._poll_once()
    client.snapshots["AAPL"] = snapshot("AAPL", 191.0)
    await source._poll_once()
    assert cache.get("AAPL").direction == "up"
    assert cache.get("AAPL").previous_price == 190.0


# --- Watchlist changes ---


async def test_add_ticker_fetches_immediately_and_seeds_cache():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5), "PYPL": snapshot("PYPL", 62.1)})
    source, cache = make_source(client)
    await source.start(["AAPL"])
    try:
        await source.add_ticker("PYPL")
        assert client.calls[-1] == (SnapshotMarketType.STOCKS, ["PYPL"])
        assert source.get_tickers() == ["AAPL", "PYPL"]
        assert cache.get_price("PYPL") == 62.1
    finally:
        await source.stop()


async def test_add_unknown_ticker_rejected():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5)})
    source, cache = make_source(client)
    await source.start(["AAPL"])
    try:
        with pytest.raises(UnknownTickerError, match="Unknown ticker: XYZ"):
            await source.add_ticker("XYZ")
        assert source.get_tickers() == ["AAPL"]
        assert "XYZ" not in cache
    finally:
        await source.stop()


async def test_add_ticker_without_price_rejected():
    client = FakeClient({"NOPX": snapshot("NOPX")})
    source, _ = make_source(client)
    await source.start([])
    with pytest.raises(UnknownTickerError):
        await source.add_ticker("NOPX")
    await source.stop()
    assert source.get_tickers() == []


async def test_add_ticker_api_failure_raises_market_data_error():
    client = FakeClient()
    source, _ = make_source(client)
    await source.start([])
    client.error = RuntimeError("503")
    with pytest.raises(MarketDataError):
        await source.add_ticker("AAPL")
    await source.stop()
    assert source.get_tickers() == []


async def test_add_existing_ticker_is_noop():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5)})
    source, _ = make_source(client)
    await source.start(["AAPL"])
    n = len(client.calls)
    await source.add_ticker("AAPL")
    await source.stop()
    assert len(client.calls) == n
    assert source.get_tickers() == ["AAPL"]


async def test_add_before_start_raises():
    source = MassiveDataSource("k", PriceCache())
    with pytest.raises(RuntimeError):
        await source.add_ticker("AAPL")


async def test_remove_ticker_clears_cache_and_next_poll():
    client = FakeClient({"AAPL": snapshot("AAPL", 190.5), "GOOGL": snapshot("GOOGL", 175.0)})
    source, cache = make_source(client)
    await source.start(["AAPL", "GOOGL"])
    await source.remove_ticker("GOOGL")
    await source._poll_once()
    await source.stop()
    assert source.get_tickers() == ["AAPL"]
    assert cache.get("GOOGL") is None
    assert client.calls[-1][1] == ["AAPL"]


async def test_remove_unknown_is_noop():
    source, _ = make_source(FakeClient())
    await source.remove_ticker("NOPE")
    assert source.get_tickers() == []


async def test_get_tickers_returns_copy():
    source, _ = make_source(FakeClient())
    await source.start(["AAPL"])
    await source.stop()
    source.get_tickers().append("X")
    assert source.get_tickers() == ["AAPL"]
