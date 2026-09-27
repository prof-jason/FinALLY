import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app

PORTFOLIO_KEYS = {"cash_balance", "total_value", "total_unrealized_pnl", "positions"}
POSITION_KEYS = {
    "ticker",
    "quantity",
    "avg_cost",
    "current_price",
    "market_value",
    "unrealized_pnl",
    "unrealized_pnl_percent",
}


def buy(client, ticker="AAPL", quantity=1, side="buy"):
    return client.post(
        "/api/portfolio/trade", json={"ticker": ticker, "side": side, "quantity": quantity}
    )


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_get_portfolio_initial(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == PORTFOLIO_KEYS
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []


def test_trade_buy_and_sell(client, cache):
    cache.update("AAPL", 100.0)
    r = buy(client, "aapl", 2.5)
    assert r.status_code == 200
    body = r.json()
    assert set(body["trade"]) == {"id", "ticker", "side", "quantity", "price", "executed_at"}
    assert body["trade"]["ticker"] == "AAPL"
    assert set(body["portfolio"]) == PORTFOLIO_KEYS
    [pos] = body["portfolio"]["positions"]
    assert set(pos) == POSITION_KEYS
    assert body["portfolio"]["cash_balance"] == 9750.0

    r = buy(client, "AAPL", 2.5, side="sell")
    assert r.status_code == 200
    assert r.json()["portfolio"]["positions"] == []
    assert r.json()["portfolio"]["cash_balance"] == 10000.0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"ticker": "AAPL", "side": "buy", "quantity": 0}, "Quantity must be greater than 0"),
        ({"ticker": "AAPL", "side": "buy", "quantity": -3}, "Quantity must be greater than 0"),
        ({"ticker": "AAPL", "side": "buy", "quantity": 1_000_000}, "Insufficient cash"),
        ({"ticker": "AAPL", "side": "sell", "quantity": 1}, "Insufficient shares"),
        ({"ticker": "AAPL", "side": "hold", "quantity": 1}, "Side must be 'buy' or 'sell'"),
        ({"ticker": "ZZZZZ", "side": "buy", "quantity": 1}, "No price available for ZZZZZ"),
        ({"ticker": "bad!", "side": "buy", "quantity": 1}, "Invalid ticker: 'bad!'"),
    ],
)
def test_trade_validation_errors(client, payload, message):
    r = client.post("/api/portfolio/trade", json=payload)
    assert r.status_code == 400
    assert r.json() == {"error": message}


@pytest.mark.parametrize(
    "payload",
    [{}, {"ticker": "AAPL"}, {"ticker": 5, "side": "buy", "quantity": 1}, "not json"],
)
def test_trade_request_validation_is_400_error_json(client, payload):
    r = client.post("/api/portfolio/trade", json=payload)
    assert r.status_code == 400
    assert set(r.json()) == {"error"}
    assert isinstance(r.json()["error"], str)


def test_trades_history_newest_first_with_limit(client, cache):
    cache.update("AAPL", 100.0)
    buy(client, "AAPL", 1)
    buy(client, "AAPL", 2)
    trades = client.get("/api/portfolio/trades").json()["trades"]
    assert [t["quantity"] for t in trades] == [2, 1]
    limited = client.get("/api/portfolio/trades?limit=1").json()["trades"]
    assert len(limited) == 1
    r = client.get("/api/portfolio/trades?limit=0")
    assert r.status_code == 400 and "error" in r.json()


def test_history_includes_trade_snapshots(client, cache):
    before = client.get("/api/portfolio/history").json()["snapshots"]
    cache.update("AAPL", 100.0)
    buy(client, "AAPL", 1)
    snaps = client.get("/api/portfolio/history").json()["snapshots"]
    assert len(snaps) == len(before) + 1
    assert set(snaps[-1]) == {"total_value", "recorded_at"}
    times = [s["recorded_at"] for s in snaps]
    assert times == sorted(times)


def test_startup_records_initial_snapshot(client):
    snaps = client.get("/api/portfolio/history").json()["snapshots"]
    assert snaps and snaps[0]["total_value"] == 10000.0


def test_reset(client, cache):
    cache.update("AAPL", 100.0)
    buy(client, "AAPL", 3)
    client.post("/api/watchlist", json={"ticker": "PYPL"})
    client.delete("/api/watchlist/GOOGL")

    r = client.post("/api/portfolio/reset")
    assert r.status_code == 200
    assert r.json() == {
        "cash_balance": 10000.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
        "positions": [],
    }
    assert client.get("/api/portfolio/trades").json()["trades"] == []
    tickers = [w["ticker"] for w in client.get("/api/watchlist").json()["watchlist"]]
    assert tickers == list(db.DEFAULT_WATCHLIST)


def test_watchlist_get(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    items = r.json()["watchlist"]
    assert [i["ticker"] for i in items] == list(db.DEFAULT_WATCHLIST)
    assert all(i["price"] is not None for i in items)


def test_watchlist_add_and_remove(client):
    r = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert r.status_code == 201
    assert r.json()["ticker"] == "PYPL"
    assert r.json()["price"] is not None

    r = client.delete("/api/watchlist/pypl")
    assert r.status_code == 204
    assert r.content == b""
    tickers = [w["ticker"] for w in client.get("/api/watchlist").json()["watchlist"]]
    assert "PYPL" not in tickers


def test_watchlist_add_existing_is_201(client):
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 201


@pytest.mark.parametrize("payload", [{"ticker": "TOOLONG"}, {"ticker": "A1"}, {}])
def test_watchlist_add_invalid(client, payload):
    r = client.post("/api/watchlist", json=payload)
    assert r.status_code == 400
    assert set(r.json()) == {"error"}


def test_watchlist_remove_missing_is_404(client):
    r = client.delete("/api/watchlist/PYPL")
    assert r.status_code == 404
    assert r.json() == {"error": "PYPL is not on the watchlist"}


def test_watchlist_remove_invalid_is_400(client):
    r = client.delete("/api/watchlist/123")
    assert r.status_code == 400


def test_removed_but_held_ticker_stays_priced(client, cache):
    cache.update("AAPL", 100.0)
    buy(client, "AAPL", 1)
    client.delete("/api/watchlist/AAPL")
    assert "AAPL" in cache
    [pos] = client.get("/api/portfolio").json()["positions"]
    assert pos["ticker"] == "AAPL"
    buy(client, "AAPL", 1, side="sell")
    assert "AAPL" not in cache


def test_unknown_route_is_404_error_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "Not Found"}


def test_method_not_allowed_is_error_json(client):
    r = client.put("/api/health")
    assert r.status_code == 405
    assert set(r.json()) == {"error"}


def test_sse_route_registered(client):
    paths = client.app.openapi()["paths"]
    assert "/api/stream/prices" in paths
    assert "/api/chat" in paths


def test_static_mounted_last_and_api_wins(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>FinAlly</html>")
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "finally.db"))
    monkeypatch.setenv("FINALLY_STATIC_DIR", str(static))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        assert c.get("/").text == "<html>FinAlly</html>"
        assert c.get("/api/health").json() == {"status": "ok"}
        assert c.app.routes[-1].name == "static"
