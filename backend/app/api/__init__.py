"""REST routers and error handling for the FinAlly API."""

from .errors import register_exception_handlers
from .health import router as health_router
from .portfolio import router as portfolio_router
from .watchlist import router as watchlist_router

__all__ = [
    "health_router",
    "portfolio_router",
    "register_exception_handlers",
    "watchlist_router",
]
