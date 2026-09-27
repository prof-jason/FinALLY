import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Terminal from "./Terminal";
import { FakeEventSource, mockFetch, portfolio, tick } from "@/test/mocks";
import type { Portfolio, Trade, WatchlistItem } from "@/lib/types";

const item = (ticker: string, price: number | null = null): WatchlistItem => ({
  ticker,
  price,
  previous_price: price,
  change: 0,
  change_percent: 0,
  direction: "flat",
  added_at: "2026-09-27T00:00:00Z",
});

const held: Portfolio = portfolio({
  cash_balance: 9000,
  total_value: 10000,
  positions: [
    { ticker: "AAPL", quantity: 5, avg_cost: 200, current_price: 200, market_value: 1000, unrealized_pnl: 0, unrealized_pnl_percent: 0 },
  ],
});

let state: { portfolio: Portfolio; watchlist: WatchlistItem[]; trades: Trade[] };

function routes() {
  return mockFetch({
    "GET /api/portfolio": () => ({ body: state.portfolio }),
    "GET /api/watchlist": () => ({ body: { watchlist: state.watchlist } }),
    "GET /api/portfolio/trades": () => ({ body: { trades: state.trades } }),
    "GET /api/portfolio/history": () => ({ body: { snapshots: [] } }),
    "POST /api/watchlist": (init) => {
      const { ticker } = JSON.parse(String(init?.body));
      if (ticker === "ZZZZ") return { status: 404, body: { error: "Unknown ticker: ZZZZ" } };
      const it = item(ticker, 50);
      state.watchlist = [...state.watchlist, it];
      return { status: 201, body: it };
    },
    "DELETE /api/watchlist/MSFT": () => {
      state.watchlist = state.watchlist.filter((w) => w.ticker !== "MSFT");
      return { status: 204 };
    },
    "POST /api/portfolio/trade": (init) => {
      const { ticker, side, quantity } = JSON.parse(String(init?.body));
      if (quantity > 100) return { status: 400, body: { error: "Insufficient cash" } };
      const trade: Trade = { id: "t1", ticker, side, quantity, price: 200, executed_at: "2026-09-27T12:00:00Z" };
      state.portfolio = held;
      state.trades = [trade];
      return { body: { trade, portfolio: held } };
    },
    "POST /api/portfolio/reset": () => {
      state = { portfolio: portfolio(), watchlist: [item("AAPL", 190), item("MSFT", 400)], trades: [] };
      return { body: state.portfolio };
    },
    "POST /api/chat": () => {
      state.watchlist = [...state.watchlist, item("PYPL", 60)];
      return {
        body: {
          message: "Adding PYPL.",
          actions: { trades: [], watchlist_changes: [{ ticker: "PYPL", action: "add", status: "executed" }] },
        },
      };
    },
  });
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  state = { portfolio: portfolio(), watchlist: [item("AAPL", 190), item("MSFT", 400)], trades: [] };
});
afterEach(() => vi.unstubAllGlobals());

describe("Terminal", () => {
  it("loads the portfolio and watchlist and shows the connection state", async () => {
    routes();
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("header-total-value")).toHaveTextContent("$10,000.00"));
    expect(screen.getByTestId("header-cash")).toHaveTextContent("$10,000.00");
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("main-chart")).toHaveAttribute("data-ticker", "AAPL");
    expect(screen.getByTestId("trade-ticker-input")).toHaveValue("AAPL");
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "reconnecting");
    act(() => FakeEventSource.latest().open());
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
  });

  it("buys shares, then values them live from the stream", async () => {
    const fetch = routes();
    render(<Terminal />);
    await screen.findByTestId("watchlist-row-AAPL");
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "5");
    await userEvent.click(screen.getByTestId("trade-buy-button"));

    expect(await screen.findByTestId("position-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("header-cash")).toHaveTextContent("$9,000.00");
    expect(await screen.findByTestId("trade-history-row")).toHaveAttribute("data-side", "buy");
    expect(screen.getByTestId("trade-success")).toHaveTextContent("Bought 5 AAPL @ 200.00");
    expect(fetch.mock.calls.some(([u]) => String(u).startsWith("/api/portfolio/trades"))).toBe(true);

    act(() => FakeEventSource.latest().emit(tick("AAPL", 210, 200)));
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("$10,050.00");
    expect(screen.getByTestId("header-pnl")).toHaveTextContent("+$50.00");
    expect(within(screen.getByTestId("position-row-AAPL")).getByText("+$50.00")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("210.00");
  });

  it("shows trade errors inline", async () => {
    routes();
    render(<Terminal />);
    await screen.findByTestId("watchlist-row-AAPL");
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "1000");
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient cash");
  });

  it("adds and removes watchlist tickers, surfacing unknown tickers", async () => {
    routes();
    render(<Terminal />);
    await screen.findByTestId("watchlist-row-MSFT");
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl{Enter}");
    expect(await screen.findByTestId("watchlist-row-PYPL")).toBeInTheDocument();

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "zzzz{Enter}");
    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent("Unknown ticker: ZZZZ");

    await userEvent.click(screen.getByTestId("watchlist-remove-MSFT"));
    await waitFor(() => expect(screen.queryByTestId("watchlist-row-MSFT")).not.toBeInTheDocument());
  });

  it("refreshes the watchlist after chat actions", async () => {
    routes();
    render(<Terminal />);
    await screen.findByTestId("watchlist-row-AAPL");
    await userEvent.type(screen.getByTestId("chat-input"), "add PYPL{Enter}");
    expect(await screen.findByTestId("watchlist-row-PYPL")).toBeInTheDocument();
  });

  it("resets to the seed state", async () => {
    state.portfolio = held;
    state.trades = [{ id: "t1", ticker: "AAPL", side: "buy", quantity: 5, price: 200, executed_at: "2026-09-27T12:00:00Z" }];
    routes();
    render(<Terminal />);
    expect(await screen.findByTestId("position-row-AAPL")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("reset-button"));
    await waitFor(() => expect(screen.queryByTestId("position-row-AAPL")).not.toBeInTheDocument());
    expect(screen.getByTestId("header-cash")).toHaveTextContent("$10,000.00");
    expect(screen.queryAllByTestId("trade-history-row")).toHaveLength(0);
  });
});
