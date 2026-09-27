import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Watchlist, { WatchlistRow } from "./Watchlist";

const history = { points: new Map(), open: new Map() };

const setup = (over: Partial<Parameters<typeof Watchlist>[0]> = {}) => {
  const props = {
    rows: [
      { ticker: "AAPL", price: 190.5, changePercent: 1.25 },
      { ticker: "TSLA", price: 250, changePercent: -0.5 },
    ],
    history,
    version: 0,
    selected: "AAPL",
    error: null,
    onSelect: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(true),
    onRemove: vi.fn(),
    ...over,
  };
  render(<Watchlist {...props} />);
  return props;
};

describe("Watchlist", () => {
  it("renders rows with price, change and selection", () => {
    setup();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("190.50");
    expect(screen.getByTestId("watchlist-change-AAPL")).toHaveTextContent("+1.25%");
    expect(screen.getByTestId("watchlist-change-TSLA")).toHaveTextContent("-0.50%");
    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveAttribute("data-selected", "true");
    expect(screen.getByTestId("watchlist-row-TSLA")).toHaveAttribute("data-selected", "false");
  });

  it("selects a ticker on click", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Show TSLA chart" }));
    expect(p.onSelect).toHaveBeenCalledWith("TSLA");
  });

  it("adds an uppercased ticker and clears the input on success", async () => {
    const p = setup();
    const input = screen.getByTestId("watchlist-add-input");
    await userEvent.type(input, "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));
    expect(p.onAdd).toHaveBeenCalledWith("PYPL");
    expect(input).toHaveValue("");
  });

  it("rejects malformed tickers without calling the API", async () => {
    const p = setup();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "AB1{Enter}");
    expect(p.onAdd).not.toHaveBeenCalled();
    expect(screen.getByTestId("watchlist-error")).toHaveTextContent("1–5 letters");
  });

  it("keeps the input and shows the server error when add fails", async () => {
    setup({ onAdd: vi.fn().mockResolvedValue(false), error: "Unknown ticker: ZZZZ" });
    expect(screen.getByTestId("watchlist-error")).toHaveTextContent("Unknown ticker: ZZZZ");
  });

  it("removes a ticker", async () => {
    const p = setup();
    await userEvent.click(screen.getByTestId("watchlist-remove-TSLA"));
    expect(p.onRemove).toHaveBeenCalledWith("TSLA");
  });

  it("shows an empty state", () => {
    setup({ rows: [] });
    expect(screen.getByText(/Add a symbol/)).toBeInTheDocument();
  });
});

describe("price flash", () => {
  const Row = ({ price }: { price: number | null }) => (
    <ul>
      <WatchlistRow
        ticker="AAPL"
        price={price}
        changePercent={0}
        selected={false}
        points={[]}
        version={price}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    </ul>
  );

  it("flashes green on uptick, red on downtick, then clears", () => {
    vi.useFakeTimers();
    const { rerender } = render(<Row price={100} />);
    const cell = screen.getByTestId("watchlist-price-AAPL");
    expect(cell).not.toHaveClass("flash-up");

    rerender(<Row price={101} />);
    expect(cell).toHaveClass("flash-up");
    expect(cell).toHaveAttribute("data-flash", "up");

    act(() => vi.advanceTimersByTime(300));
    expect(cell).not.toHaveClass("flash-up");
    expect(cell).not.toHaveAttribute("data-flash");

    rerender(<Row price={99} />);
    expect(cell).toHaveClass("flash-down");

    // Same price again: no new flash.
    act(() => vi.advanceTimersByTime(300));
    rerender(<Row price={99} />);
    expect(cell).not.toHaveClass("flash-down");
    vi.useRealTimers();
  });

  it("does not flash on the first price", () => {
    const { rerender } = render(<Row price={null} />);
    rerender(<Row price={100} />);
    expect(screen.getByTestId("watchlist-price-AAPL")).not.toHaveAttribute("data-flash");
  });
});
