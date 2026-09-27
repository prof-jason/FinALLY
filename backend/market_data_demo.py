"""Live terminal dashboard for the market data backend.

Starts the configured data source (simulator, or Massive when MASSIVE_API_KEY
is set in the environment), reads the shared PriceCache the same way the SSE
endpoint does, and renders prices, sparklines, direction arrows and an event
log of notable moves.

    uv run market_data_demo.py                      # 60s, default watchlist
    uv run market_data_demo.py --duration 0         # run until Ctrl+C
    uv run market_data_demo.py --event-prob 0.01    # more random shocks
    uv run market_data_demo.py --tickers AAPL TSLA PYPL
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import deque
from datetime import datetime

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.market import (
    MassiveDataSource,
    PriceCache,
    PriceUpdate,
    SimulatorDataSource,
    create_market_data_source,
    normalize_ticker,
)
from app.market.seed_prices import SEED_PRICES

SPARK_CHARS = "▁▂▃▄▅▆▇█"
SPARK_WIDTH = 40
EVENT_LOG_SIZE = 10
REFRESH_SECONDS = 0.25


def sparkline(prices: deque[float]) -> Text:
    """Render prices as unicode blocks scaled to their own min/max."""
    if len(prices) < 2:
        return Text("·" * len(prices), style="dim")
    lo, hi = min(prices), max(prices)
    span = hi - lo
    chars = "".join(
        SPARK_CHARS[int((p - lo) / span * (len(SPARK_CHARS) - 1))] if span else SPARK_CHARS[3]
        for p in prices
    )
    style = "green" if prices[-1] > prices[0] else "red" if prices[-1] < prices[0] else "yellow"
    return Text(chars, style=style)


def arrow(direction: str) -> Text:
    return {
        "up": Text("▲", style="bold green"),
        "down": Text("▼", style="bold red"),
    }.get(direction, Text("●", style="dim"))


class Dashboard:
    """Accumulates cache updates into history, stats and an event log."""

    def __init__(self, cache: PriceCache, source_name: str, threshold: float) -> None:
        self.cache = cache
        self.source_name = source_name
        self.threshold = threshold
        self.started = time.monotonic()
        self.history: dict[str, deque[float]] = {}
        self.first_price: dict[str, float] = {}
        self.last_seen: dict[str, float] = {}
        self.events: deque[Text] = deque(maxlen=EVENT_LOG_SIZE)
        self.update_count = 0

    def poll(self) -> None:
        """Pull new updates from the cache; record history and notable moves."""
        for ticker, update in self.cache.get_all().items():
            if self.last_seen.get(ticker) == update.timestamp:
                continue
            self.last_seen[ticker] = update.timestamp
            self.update_count += 1
            self.history.setdefault(ticker, deque(maxlen=SPARK_WIDTH)).append(update.price)
            self.first_price.setdefault(ticker, update.price)
            if abs(update.change_percent) >= self.threshold:
                self.log_event(update)

    def log_event(self, update: PriceUpdate) -> None:
        color = "green" if update.direction == "up" else "red"
        line = Text()
        line.append(datetime.now().strftime("%H:%M:%S "), style="dim")
        line.append_text(arrow(update.direction))
        line.append(f" {update.ticker:<5}", style="bold")
        line.append(f" {update.change_percent:+.2f}%", style=f"bold {color}")
        line.append(f"  ${update.previous_price:,.2f} → ${update.price:,.2f}")
        self.events.appendleft(line)

    def render(self) -> Group:
        elapsed = time.monotonic() - self.started

        table = Table(expand=True, header_style="bold #ecad0a", border_style="#30363d")
        table.add_column("Ticker", style="bold #209dd7")
        table.add_column("Price", justify="right")
        table.add_column("", justify="center", width=2)
        table.add_column("Tick Δ", justify="right")
        table.add_column("Session %", justify="right")
        table.add_column(f"Sparkline (last {SPARK_WIDTH})", no_wrap=True)

        prices = self.cache.get_all()
        for ticker, update in sorted(prices.items()):
            tick_style = {"up": "green", "down": "red"}.get(update.direction, "dim")
            session = (update.price / self.first_price.get(ticker, update.price) - 1) * 100
            session_style = "green" if session > 0 else "red" if session < 0 else "dim"
            table.add_row(
                ticker,
                f"${update.price:,.2f}",
                arrow(update.direction),
                Text(f"{update.change:+.2f}", style=tick_style),
                Text(f"{session:+.2f}%", style=session_style),
                sparkline(self.history.get(ticker, deque())),
            )

        rate = self.update_count / elapsed if elapsed > 0 else 0.0
        subtitle = (
            f"{self.source_name} · {len(prices)} tickers · {self.update_count} updates "
            f"({rate:.1f}/s) · cache v{self.cache.version} · {elapsed:.0f}s"
        )
        events = self.events or [Text("No notable moves yet…", style="dim")]
        return Group(
            Panel(
                table,
                title="[bold]FinAlly · Market Data[/]",
                subtitle=subtitle,
                border_style="#209dd7",
            ),
            Panel(
                Group(*events), title=f"Events (|move| ≥ {self.threshold}%)", border_style="#753991"
            ),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--duration", type=float, default=60.0, help="seconds to run; 0 = until Ctrl+C (default 60)"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=list(SEED_PRICES),
        help="tickers to track (default: the 10-ticker watchlist)",
    )
    parser.add_argument(
        "--event-prob",
        type=float,
        default=None,
        help="simulator shock probability per ticker per tick (default 0.001)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="log moves at least this many percent (default 1.0)",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    console = Console()
    tickers = list(dict.fromkeys(normalize_ticker(t) for t in args.tickers))

    cache = PriceCache()
    source = create_market_data_source(cache)
    if isinstance(source, SimulatorDataSource) and args.event_prob is not None:
        source = SimulatorDataSource(cache, event_probability=args.event_prob)
    source_name = "Massive API" if isinstance(source, MassiveDataSource) else "GBM simulator"

    await source.start(tickers)
    dashboard = Dashboard(cache, source_name, args.threshold)
    dashboard.poll()
    deadline = time.monotonic() + args.duration if args.duration > 0 else None
    try:
        with Live(dashboard.render(), console=console, refresh_per_second=4, screen=False) as live:
            while deadline is None or time.monotonic() < deadline:
                dashboard.poll()
                live.update(dashboard.render())
                await asyncio.sleep(REFRESH_SECONDS)
    finally:
        await source.stop()

    console.print(
        f"[dim]Done: {dashboard.update_count} updates, "
        f"{len(dashboard.events)} events logged, cache v{cache.version}.[/]"
    )


def main() -> None:
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
