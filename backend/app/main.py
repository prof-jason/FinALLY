"""FastAPI entry point: API routers, SSE stream, background tasks, static frontend."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db, services
from app.api import health_router, portfolio_router, register_exception_handlers, watchlist_router
from app.market import PriceCache, create_market_data_source, create_stream_router

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _static_dir() -> Path:
    return Path(os.environ.get("FINALLY_STATIC_DIR", BACKEND_DIR / "static"))


def create_app() -> FastAPI:
    price_cache = PriceCache()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db.init_db()
        source = create_market_data_source(price_cache)
        services.state.configure(price_cache, source)
        with db.get_connection() as conn:
            tickers = services.tracked_tickers(conn)
        await source.start(tickers)
        snapshot_task = services.start_snapshot_task()
        logger.info("FinAlly started, tracking %d tickers", len(tickers))
        try:
            yield
        finally:
            await services.stop_snapshot_task(snapshot_task)
            await source.stop()
            services.state.clear()

    app = FastAPI(title="FinAlly", lifespan=lifespan)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(watchlist_router)
    app.include_router(create_stream_router(price_cache))
    try:
        from app.llm import create_chat_router
    except ModuleNotFoundError as exc:
        if exc.name != "app.llm":
            raise
        logger.warning("app.llm not available; /api/chat is disabled")
    else:
        app.include_router(create_chat_router())

    # Mounted last so every /api route takes precedence
    static_dir = _static_dir()
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
