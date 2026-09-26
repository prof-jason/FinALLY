import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES
from app.market.simulator import SimulatorDataSource


@pytest.fixture
async def source():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=0.01, seed=1)
    yield src, cache
    await src.stop()


async def test_start_seeds_cache_immediately(source):
    src, cache = source
    await src.start(["AAPL", "GOOGL"])
    assert cache.get_price("AAPL") == SEED_PRICES["AAPL"]
    assert cache.get_price("GOOGL") == SEED_PRICES["GOOGL"]
    assert cache.get("AAPL").direction == "flat"


async def test_prices_update_over_time(source):
    src, cache = source
    await src.start(["AAPL"])
    v0 = cache.version
    await asyncio.sleep(0.1)
    assert cache.version > v0
    assert cache.get("AAPL").timestamp > 0


async def test_get_tickers(source):
    src, _ = source
    assert src.get_tickers() == []
    await src.start(["AAPL", "MSFT"])
    assert src.get_tickers() == ["AAPL", "MSFT"]


async def test_add_ticker_seeds_cache_immediately(source):
    src, cache = source
    await src.start(["AAPL"])
    await src.add_ticker("PYPL")
    assert "PYPL" in src.get_tickers()
    assert 50.0 <= cache.get_price("PYPL") <= 500.0


async def test_add_existing_ticker_is_noop(source):
    src, cache = source
    await src.start(["AAPL"])
    v = cache.version
    await src.add_ticker("AAPL")
    assert src.get_tickers() == ["AAPL"]
    assert cache.version == v


async def test_remove_ticker_clears_cache(source):
    src, cache = source
    await src.start(["AAPL", "TSLA"])
    await src.remove_ticker("TSLA")
    assert src.get_tickers() == ["AAPL"]
    assert cache.get("TSLA") is None
    await asyncio.sleep(0.05)
    assert cache.get("TSLA") is None  # loop does not resurrect it


async def test_remove_unknown_is_noop(source):
    src, _ = source
    await src.start(["AAPL"])
    await src.remove_ticker("NOPE")
    assert src.get_tickers() == ["AAPL"]


async def test_add_before_start_raises():
    src = SimulatorDataSource(price_cache=PriceCache())
    with pytest.raises(RuntimeError):
        await src.add_ticker("AAPL")


async def test_start_with_empty_list(source):
    src, cache = source
    await src.start([])
    await asyncio.sleep(0.03)
    assert len(cache) == 0
    await src.add_ticker("AAPL")
    assert cache.get_price("AAPL") == SEED_PRICES["AAPL"]


async def test_stop_halts_updates_and_is_idempotent(source):
    src, cache = source
    await src.start(["AAPL"])
    await asyncio.sleep(0.03)
    await src.stop()
    v = cache.version
    await asyncio.sleep(0.05)
    assert cache.version == v
    await src.stop()


async def test_stop_before_start_is_safe():
    await SimulatorDataSource(price_cache=PriceCache()).stop()


async def test_loop_survives_step_exception(source, monkeypatch):
    src, cache = source
    await src.start(["AAPL"])
    calls = {"n": 0}
    real_step = src._sim.step

    def flaky_step():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_step()

    monkeypatch.setattr(src._sim, "step", flaky_step)
    v = cache.version
    await asyncio.sleep(0.1)
    assert calls["n"] > 1
    assert cache.version > v
