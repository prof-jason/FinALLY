import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.market.cache import PriceCache
from app.market.stream import create_stream_router, format_prices_event, generate_events


class FakeRequest:
    """Minimal Request stand-in that disconnects after `polls` checks."""

    def __init__(self, polls: int, on_poll=None):
        self.client = SimpleNamespace(host="127.0.0.1")
        self._remaining = polls
        self._on_poll = on_poll
        self.checks = 0

    async def is_disconnected(self) -> bool:
        if self._on_poll:
            self._on_poll(self.checks)
        self.checks += 1
        self._remaining -= 1
        return self._remaining < 0


async def collect(cache, request, interval=0.0):
    return [event async for event in generate_events(cache, request, interval)]


def parse(event: str) -> dict:
    assert event.startswith("data: ") and event.endswith("\n\n")
    return json.loads(event[len("data: ") :])


def test_format_prices_event():
    cache = PriceCache()
    cache.update("AAPL", 190.0, timestamp=1.0)
    cache.update("AAPL", 191.0, timestamp=2.0)
    payload = parse(format_prices_event(cache))
    assert payload == {
        "AAPL": {
            "ticker": "AAPL",
            "price": 191.0,
            "previous_price": 190.0,
            "timestamp": 2.0,
            "change": 1.0,
            "change_percent": 0.5263,
            "direction": "up",
        }
    }


async def test_first_event_is_retry_directive():
    events = await collect(PriceCache(), FakeRequest(polls=0))
    assert events == ["retry: 1000\n\n"]


async def test_sends_prices_then_skips_unchanged_ticks():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    events = await collect(cache, FakeRequest(polls=5))
    assert len(events) == 2  # retry + a single data event; no repeats while unchanged
    assert set(parse(events[1])) == {"AAPL", "GOOGL"}


async def test_sends_new_event_when_cache_changes():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    def mutate(check):
        if check == 2:
            cache.update("AAPL", 191.0)

    events = await collect(cache, FakeRequest(polls=5, on_poll=mutate))
    data = [parse(e) for e in events[1:]]
    assert [d["AAPL"]["price"] for d in data] == [190.0, 191.0]
    assert data[1]["AAPL"]["direction"] == "up"


async def test_removal_of_last_ticker_sends_empty_event():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    def mutate(check):
        if check == 2:
            cache.remove("AAPL")

    events = await collect(cache, FakeRequest(polls=5, on_poll=mutate))
    assert parse(events[-1]) == {}


async def test_stops_on_disconnect():
    request = FakeRequest(polls=3)
    await collect(PriceCache(), request)
    assert request.checks == 4


async def test_missing_client_info():
    request = FakeRequest(polls=0)
    request.client = None
    assert await collect(PriceCache(), request) == ["retry: 1000\n\n"]


def test_router_registers_prices_route():
    app = FastAPI()
    app.include_router(create_stream_router(PriceCache()))
    assert "get" in app.openapi()["paths"]["/api/stream/prices"]


def test_router_factory_is_not_shared():
    r1 = create_stream_router(PriceCache())
    r2 = create_stream_router(PriceCache())
    assert r1 is not r2
    assert len(r1.routes) == len(r2.routes) == 1


async def test_endpoint_returns_event_stream():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    router = create_stream_router(cache, interval=0.0)
    endpoint = router.routes[0].endpoint
    response = await endpoint(FakeRequest(polls=1))
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    body = [chunk async for chunk in response.body_iterator]
    assert body[0] == "retry: 1000\n\n"
    assert parse(body[1])["AAPL"]["price"] == 190.0
