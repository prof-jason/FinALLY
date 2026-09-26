import pytest

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.delenv("MASSIVE_POLL_INTERVAL", raising=False)


def test_no_key_uses_simulator():
    assert isinstance(create_market_data_source(PriceCache()), SimulatorDataSource)


@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_blank_key_uses_simulator(monkeypatch, value):
    monkeypatch.setenv("MASSIVE_API_KEY", value)
    assert isinstance(create_market_data_source(PriceCache()), SimulatorDataSource)


def test_key_uses_massive(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "  abc123  ")
    source = create_market_data_source(PriceCache())
    assert isinstance(source, MassiveDataSource)
    assert source._api_key == "abc123"
    assert source._interval == 15.0


def test_poll_interval_override(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "abc123")
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL", "5")
    assert create_market_data_source(PriceCache())._interval == 5.0


def test_source_shares_the_cache(monkeypatch):
    cache = PriceCache()
    assert create_market_data_source(cache)._cache is cache
    monkeypatch.setenv("MASSIVE_API_KEY", "abc123")
    assert create_market_data_source(cache)._cache is cache


def test_returns_unstarted_source():
    source = create_market_data_source(PriceCache())
    assert source.get_tickers() == []
    assert source._task is None
