"""SSE endpoint streaming live prices from the PriceCache."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # Disable proxy buffering
}


def create_stream_router(price_cache: PriceCache, interval: float = 0.5) -> APIRouter:
    """Build a router exposing GET /api/stream/prices bound to `price_cache`.

    A fresh router is created per call, so calling this twice (e.g. in tests)
    never double-registers the route.
    """
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """Stream all tracked prices as SSE events.

        Each event's data is a JSON object keyed by ticker:
            data: {"AAPL": {"ticker": "AAPL", "price": 190.5, ...}, ...}
        """
        return StreamingResponse(
            generate_events(price_cache, request, interval),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    return router


def format_prices_event(price_cache: PriceCache) -> str:
    """Serialize every cached price as one SSE `data:` event."""
    data = {ticker: update.to_dict() for ticker, update in price_cache.get_all().items()}
    return f"data: {json.dumps(data)}\n\n"


async def generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Yield SSE events whenever the cache changes, until the client disconnects.

    The cache is checked every `interval` seconds; nothing is sent when its
    version is unchanged (e.g. between 15s Massive polls). An event is sent
    even when the cache is empty so removals of the last ticker propagate.
    """
    # Browser EventSource reconnects after 1s if the connection drops
    yield "retry: 1000\n\n"

    last_version = -1
    client = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client)

    try:
        while not await request.is_disconnected():
            version = price_cache.version
            if version != last_version:
                last_version = version
                yield format_prices_event(price_cache)
            await asyncio.sleep(interval)
    finally:
        logger.info("SSE client disconnected: %s", client)
