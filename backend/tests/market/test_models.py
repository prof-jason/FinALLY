import dataclasses
import time

import pytest

from app.market.models import PriceUpdate


def test_direction_up():
    u = PriceUpdate("AAPL", price=191.0, previous_price=190.0, timestamp=1.0)
    assert u.direction == "up"
    assert u.change == 1.0


def test_direction_down():
    u = PriceUpdate("AAPL", price=189.0, previous_price=190.0, timestamp=1.0)
    assert u.direction == "down"
    assert u.change == -1.0


def test_direction_flat():
    u = PriceUpdate("AAPL", price=190.0, previous_price=190.0, timestamp=1.0)
    assert u.direction == "flat"
    assert u.change == 0.0
    assert u.change_percent == 0.0


def test_change_percent():
    u = PriceUpdate("AAPL", price=110.0, previous_price=100.0, timestamp=1.0)
    assert u.change_percent == pytest.approx(10.0)


def test_change_percent_zero_previous_price():
    u = PriceUpdate("AAPL", price=5.0, previous_price=0.0, timestamp=1.0)
    assert u.change_percent == 0.0


def test_change_is_rounded():
    u = PriceUpdate("AAPL", price=0.3, previous_price=0.1, timestamp=1.0)
    assert u.change == 0.2  # not 0.19999999999999998


def test_timestamp_defaults_to_now():
    before = time.time()
    ts = PriceUpdate("AAPL", 1.0, 1.0).timestamp
    assert before <= ts <= time.time()


def test_frozen():
    u = PriceUpdate("AAPL", 1.0, 1.0, 1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        u.price = 2.0  # type: ignore[misc]


def test_equality():
    assert PriceUpdate("AAPL", 1.0, 1.0, 1.0) == PriceUpdate("AAPL", 1.0, 1.0, 1.0)


def test_to_dict():
    u = PriceUpdate("AAPL", price=191.0, previous_price=190.0, timestamp=1700000000.0)
    assert u.to_dict() == {
        "ticker": "AAPL",
        "price": 191.0,
        "previous_price": 190.0,
        "timestamp": 1700000000.0,
        "change": 1.0,
        "change_percent": pytest.approx(0.5263, abs=1e-4),
        "direction": "up",
    }
