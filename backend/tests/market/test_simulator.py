import math

import numpy as np
import pytest

from app.market.seed_prices import (
    CROSS_GROUP_CORR,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
    UNKNOWN_SEED_PRICE_RANGE,
)
from app.market.simulator import GBMSimulator

DEFAULT_TICKERS = list(SEED_PRICES)


def test_dt_is_half_second_of_trading_year():
    assert GBMSimulator.DEFAULT_DT == pytest.approx(0.5 / 5_896_800)


def test_step_returns_all_tickers():
    sim = GBMSimulator(["AAPL", "GOOGL"], seed=1)
    assert set(sim.step()) == {"AAPL", "GOOGL"}


def test_empty_step():
    assert GBMSimulator([]).step() == {}


def test_initial_prices_match_seeds():
    sim = GBMSimulator(DEFAULT_TICKERS)
    for ticker, seed_price in SEED_PRICES.items():
        assert sim.get_price(ticker) == seed_price


def test_unknown_ticker_gets_random_seed_in_range():
    lo, hi = UNKNOWN_SEED_PRICE_RANGE
    assert (lo, hi) == (50.0, 500.0)
    for i in range(50):
        price = GBMSimulator(["ZZZZ"], seed=i).get_price("ZZZZ")
        assert lo <= price <= hi


def test_unknown_ticker_uses_default_params():
    sim = GBMSimulator(["ZZZZ"])
    assert sim._params["ZZZZ"] == {"sigma": 0.25, "mu": 0.05}


def test_params_are_copies():
    sim = GBMSimulator(["AAPL"])
    sim._params["AAPL"]["sigma"] = 99
    assert TICKER_PARAMS["AAPL"]["sigma"] == 0.22


def test_step_matches_gbm_formula():
    """One step with a known Z must equal S * exp((mu - sigma^2/2) dt + sigma sqrt(dt) Z)."""
    dt = 1 / 252
    sim = GBMSimulator(["AAPL"], dt=dt, event_probability=0.0, seed=42)
    z = np.random.default_rng(42).standard_normal(1)[0]
    mu, sigma = TICKER_PARAMS["AAPL"]["mu"], TICKER_PARAMS["AAPL"]["sigma"]
    expected = SEED_PRICES["AAPL"] * math.exp(
        (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z
    )

    result = sim.step()

    assert sim.get_price("AAPL") == pytest.approx(expected)
    assert result["AAPL"] == round(expected, 2)


def test_log_returns_have_expected_mean_and_volatility():
    dt = 1 / 252
    n = 20_000
    sim = GBMSimulator(["TSLA"], dt=dt, event_probability=0.0, seed=7)
    log_returns = []
    prev = sim.get_price("TSLA")
    for _ in range(n):
        sim.step()
        cur = sim.get_price("TSLA")
        log_returns.append(math.log(cur / prev))
        prev = cur
    mu, sigma = TICKER_PARAMS["TSLA"]["mu"], TICKER_PARAMS["TSLA"]["sigma"]
    arr = np.array(log_returns)
    assert arr.std() / math.sqrt(dt) == pytest.approx(sigma, rel=0.03)
    # Standard error of the mean is sigma*sqrt(dt)/sqrt(n); allow 4 SEs
    se = sigma * math.sqrt(dt) / math.sqrt(n)
    assert abs(arr.mean() - (mu - 0.5 * sigma**2) * dt) < 4 * se


def test_prices_stay_positive():
    sim = GBMSimulator(["TSLA"], dt=1 / 252, event_probability=0.05, seed=3)
    for _ in range(5_000):
        assert sim.step()["TSLA"] > 0


def test_prices_rounded_to_cents():
    sim = GBMSimulator(DEFAULT_TICKERS, seed=5)
    for price in sim.step().values():
        assert price == round(price, 2)


def test_prices_change_over_time():
    sim = GBMSimulator(["AAPL"], seed=11)
    for _ in range(1_000):
        sim.step()
    assert sim.get_price("AAPL") != SEED_PRICES["AAPL"]


def test_default_tick_moves_are_small():
    sim = GBMSimulator(["NVDA"], event_probability=0.0, seed=2)
    prev = sim.get_price("NVDA")
    for _ in range(1_000):
        sim.step()
        cur = sim.get_price("NVDA")
        assert abs(cur / prev - 1) < 0.005
        prev = cur


def test_seed_makes_runs_reproducible():
    a = GBMSimulator(DEFAULT_TICKERS, seed=123)
    b = GBMSimulator(DEFAULT_TICKERS, seed=123)
    for _ in range(50):
        assert a.step() == b.step()


def test_random_events_fire_with_expected_magnitude():
    sim = GBMSimulator(["AAPL"], dt=1e-12, event_probability=1.0, seed=9)
    prev = sim.get_price("AAPL")
    for _ in range(200):
        sim.step()
        cur = sim.get_price("AAPL")
        move = abs(cur / prev - 1)
        assert 0.0199 <= move <= 0.0501
        prev = cur


def test_no_events_when_probability_zero():
    sim = GBMSimulator(["AAPL"], dt=1e-12, event_probability=0.0, seed=9)
    for _ in range(200):
        sim.step()
    assert sim.get_price("AAPL") == pytest.approx(SEED_PRICES["AAPL"], rel=1e-4)


def test_add_ticker():
    sim = GBMSimulator(["AAPL"])
    sim.add_ticker("TSLA")
    assert "TSLA" in sim.step()
    assert sim.get_tickers() == ["AAPL", "TSLA"]


def test_add_duplicate_is_noop():
    sim = GBMSimulator(["AAPL"])
    sim.step()
    price = sim.get_price("AAPL")
    sim.add_ticker("AAPL")
    assert sim.get_tickers() == ["AAPL"]
    assert sim.get_price("AAPL") == price


def test_duplicate_initial_tickers_deduplicated():
    assert GBMSimulator(["AAPL", "AAPL"]).get_tickers() == ["AAPL"]


def test_remove_ticker():
    sim = GBMSimulator(["AAPL", "GOOGL"])
    sim.remove_ticker("GOOGL")
    result = sim.step()
    assert "GOOGL" not in result
    assert "AAPL" in result
    assert sim.get_price("GOOGL") is None


def test_remove_nonexistent_is_noop():
    sim = GBMSimulator(["AAPL"])
    sim.remove_ticker("NOPE")
    assert sim.get_tickers() == ["AAPL"]


def test_get_tickers_returns_copy():
    sim = GBMSimulator(["AAPL"])
    sim.get_tickers().append("X")
    assert sim.get_tickers() == ["AAPL"]


def test_cholesky_rebuilt_on_add_and_remove():
    sim = GBMSimulator(["AAPL"])
    assert sim._cholesky is None
    sim.add_ticker("GOOGL")
    assert sim._cholesky.shape == (2, 2)
    sim.add_ticker("JPM")
    assert sim._cholesky.shape == (3, 3)
    sim.remove_ticker("JPM")
    sim.remove_ticker("GOOGL")
    assert sim._cholesky is None


def test_cholesky_valid_for_default_tickers_plus_unknowns():
    tickers = DEFAULT_TICKERS + ["PYPL", "ZZZZ", "ABC"]
    sim = GBMSimulator(tickers)
    L = sim._cholesky
    corr = L @ L.T
    assert np.allclose(np.diag(corr), 1.0)
    i, j = tickers.index("AAPL"), tickers.index("MSFT")
    assert corr[i, j] == pytest.approx(INTRA_TECH_CORR)


@pytest.mark.parametrize(
    ("t1", "t2", "expected"),
    [
        ("AAPL", "MSFT", INTRA_TECH_CORR),
        ("NVDA", "NFLX", INTRA_TECH_CORR),
        ("JPM", "V", INTRA_FINANCE_CORR),
        ("AAPL", "JPM", CROSS_GROUP_CORR),
        ("TSLA", "AAPL", TSLA_CORR),
        ("JPM", "TSLA", TSLA_CORR),
        ("ZZZZ", "AAPL", CROSS_GROUP_CORR),
        ("ZZZZ", "YYYY", CROSS_GROUP_CORR),
    ],
)
def test_pairwise_correlation(t1, t2, expected):
    assert GBMSimulator._pairwise_correlation(t1, t2) == expected
    assert GBMSimulator._pairwise_correlation(t2, t1) == expected


def test_empirical_correlation_matches_structure():
    tickers = ["AAPL", "MSFT", "JPM", "V"]
    sim = GBMSimulator(tickers, dt=1 / 252, event_probability=0.0, seed=21)
    prev = {t: sim.get_price(t) for t in tickers}
    rets = {t: [] for t in tickers}
    for _ in range(20_000):
        sim.step()
        for t in tickers:
            cur = sim.get_price(t)
            rets[t].append(math.log(cur / prev[t]))
            prev[t] = cur
    c = np.corrcoef([rets[t] for t in tickers])
    assert c[0, 1] == pytest.approx(INTRA_TECH_CORR, abs=0.03)
    assert c[2, 3] == pytest.approx(INTRA_FINANCE_CORR, abs=0.03)
    assert c[0, 2] == pytest.approx(CROSS_GROUP_CORR, abs=0.03)
