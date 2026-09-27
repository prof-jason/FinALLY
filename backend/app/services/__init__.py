"""Business logic shared by the REST API and the LLM chat service.

Public API:
    ServiceError            - User-facing error carrying an HTTP status
    state                   - Holder for the shared PriceCache / MarketDataSource
    execute_trade           - async; market order -> {"trade", "portfolio"}
    add_watchlist_ticker    - async; add + start tracking -> watchlist item
    remove_watchlist_ticker - async; remove, keep tracking while held
    reset_portfolio         - async; restore seed state -> portfolio
    get_portfolio, get_watchlist, get_history, get_trades - sync reads
    tracked_tickers         - watchlist ∪ open positions
"""

from . import state
from .errors import ServiceError
from .portfolio import (
    execute_trade,
    get_history,
    get_portfolio,
    get_trades,
    record_snapshot,
    reset_portfolio,
)
from .snapshots import snapshot_loop, start_snapshot_task, stop_snapshot_task
from .tracking import parse_ticker, tracked_tickers
from .watchlist import add_watchlist_ticker, get_watchlist, remove_watchlist_ticker

__all__ = [
    "ServiceError",
    "add_watchlist_ticker",
    "execute_trade",
    "get_history",
    "get_portfolio",
    "get_trades",
    "get_watchlist",
    "parse_ticker",
    "record_snapshot",
    "remove_watchlist_ticker",
    "reset_portfolio",
    "snapshot_loop",
    "start_snapshot_task",
    "state",
    "stop_snapshot_task",
    "tracked_tickers",
]
