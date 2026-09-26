"""Select the market data source from the environment."""

from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create an unstarted data source based on MASSIVE_API_KEY.

    - MASSIVE_API_KEY set and non-empty -> MassiveDataSource (real market data)
    - Otherwise -> SimulatorDataSource (GBM simulation)

    MASSIVE_POLL_INTERVAL (seconds, default 15) tunes the Massive poll rate.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15") or 15)
        logger.info("Market data source: Massive API (poll every %.1fs)", interval)
        return MassiveDataSource(api_key=api_key, price_cache=price_cache, poll_interval=interval)

    logger.info("Market data source: GBM simulator")
    return SimulatorDataSource(price_cache=price_cache)
