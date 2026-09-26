"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate               - Immutable price snapshot
    PriceCache                - Thread-safe in-memory price store
    MarketDataSource          - Abstract interface for data providers
    SimulatorDataSource       - GBM simulator implementation
    MassiveDataSource         - Massive (Polygon.io) REST implementation
    create_market_data_source - Picks simulator or Massive from MASSIVE_API_KEY
    create_stream_router      - FastAPI router for GET /api/stream/prices
    normalize_ticker          - Uppercase + validate ^[A-Z]{1,5}$
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .models import PriceUpdate
from .simulator import GBMSimulator, SimulatorDataSource
from .stream import create_stream_router
from .tickers import (
    InvalidTickerError,
    MarketDataError,
    UnknownTickerError,
    normalize_ticker,
)

__all__ = [
    "GBMSimulator",
    "InvalidTickerError",
    "MarketDataError",
    "MarketDataSource",
    "MassiveDataSource",
    "PriceCache",
    "PriceUpdate",
    "SimulatorDataSource",
    "UnknownTickerError",
    "create_market_data_source",
    "create_stream_router",
    "normalize_ticker",
]
