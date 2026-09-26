import threading

from app.market.cache import PriceCache


def test_update_and_get():
    cache = PriceCache()
    update = cache.update("AAPL", 190.50, timestamp=100.0)
    assert update.ticker == "AAPL"
    assert update.price == 190.50
    assert update.timestamp == 100.0
    assert cache.get("AAPL") == update


def test_first_update_is_flat():
    update = PriceCache().update("AAPL", 190.50)
    assert update.direction == "flat"
    assert update.previous_price == 190.50


def test_previous_price_tracks_last_update():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    up = cache.update("AAPL", 191.0)
    assert (up.previous_price, up.direction, up.change) == (190.0, "up", 1.0)
    down = cache.update("AAPL", 189.0)
    assert (down.previous_price, down.direction, down.change) == (191.0, "down", -2.0)


def test_prices_rounded_to_cents():
    assert PriceCache().update("AAPL", 190.12678).price == 190.13


def test_zero_timestamp_is_respected():
    assert PriceCache().update("AAPL", 1.0, timestamp=0.0).timestamp == 0.0


def test_missing_ticker():
    cache = PriceCache()
    assert cache.get("NOPE") is None
    assert cache.get_price("NOPE") is None


def test_get_price():
    cache = PriceCache()
    cache.update("AAPL", 190.50)
    assert cache.get_price("AAPL") == 190.50


def test_get_all_returns_copy():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    snapshot = cache.get_all()
    assert set(snapshot) == {"AAPL", "GOOGL"}
    snapshot.clear()
    assert len(cache) == 2


def test_remove():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.remove("AAPL")
    assert cache.get("AAPL") is None
    assert "AAPL" not in cache
    cache.remove("AAPL")  # no-op


def test_remove_then_readd_starts_flat():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.remove("AAPL")
    assert cache.update("AAPL", 200.0).direction == "flat"


def test_version_increments_on_update_and_remove():
    cache = PriceCache()
    v0 = cache.version
    cache.update("AAPL", 190.0)
    assert cache.version == v0 + 1
    cache.remove("AAPL")
    assert cache.version == v0 + 2
    cache.remove("AAPL")  # absent: no change
    assert cache.version == v0 + 2


def test_len_and_contains():
    cache = PriceCache()
    assert len(cache) == 0
    cache.update("AAPL", 1.0)
    assert len(cache) == 1
    assert "AAPL" in cache
    assert "MSFT" not in cache


def test_concurrent_writers():
    cache = PriceCache()
    n_threads, n_updates = 8, 500

    def writer(i: int) -> None:
        for j in range(n_updates):
            cache.update(f"T{i}", 100.0 + j)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert cache.version == n_threads * n_updates
    assert len(cache) == n_threads
    for i in range(n_threads):
        assert cache.get_price(f"T{i}") == 100.0 + n_updates - 1
