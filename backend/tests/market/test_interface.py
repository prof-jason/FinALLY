import inspect

import pytest

from app.market.interface import MarketDataSource
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource

ABSTRACT = {"start", "stop", "add_ticker", "remove_ticker", "get_tickers"}


def test_cannot_instantiate_abc():
    with pytest.raises(TypeError):
        MarketDataSource()  # type: ignore[abstract]


def test_abstract_methods():
    assert MarketDataSource.__abstractmethods__ == ABSTRACT


@pytest.mark.parametrize("impl", [SimulatorDataSource, MassiveDataSource])
def test_implementations_conform(impl):
    assert issubclass(impl, MarketDataSource)
    assert not impl.__abstractmethods__
    for name in ABSTRACT - {"get_tickers"}:
        assert inspect.iscoroutinefunction(getattr(impl, name)), name
    assert not inspect.iscoroutinefunction(impl.get_tickers)
