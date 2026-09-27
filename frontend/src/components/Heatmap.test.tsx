import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Heatmap, { heatColor } from "./Heatmap";
import type { Position } from "@/lib/types";

const pos = (ticker: string, market_value: number, pct: number): Position => ({
  ticker,
  quantity: 1,
  avg_cost: market_value,
  current_price: market_value,
  market_value,
  unrealized_pnl: (market_value * pct) / 100,
  unrealized_pnl_percent: pct,
});

describe("Heatmap", () => {
  it("renders a cell per position, sized by weight and toned by P&L", () => {
    render(<Heatmap positions={[pos("AAPL", 3000, 2), pos("TSLA", 1000, -4), pos("V", 1000, 0)]} size={{ width: 500, height: 200 }} />);
    const aapl = screen.getByTestId("heatmap-cell-AAPL");
    const tsla = screen.getByTestId("heatmap-cell-TSLA");
    expect(aapl).toHaveAttribute("data-pnl", "positive");
    expect(tsla).toHaveAttribute("data-pnl", "negative");
    expect(screen.getByTestId("heatmap-cell-V")).toHaveAttribute("data-pnl", "flat");
    const area = (el: HTMLElement) => parseFloat(el.style.width) * parseFloat(el.style.height);
    expect(area(aapl) / area(tsla)).toBeCloseTo(3, 1);
  });

  it("shows an empty state with no positions", () => {
    render(<Heatmap positions={[]} size={{ width: 500, height: 200 }} />);
    expect(screen.getByTestId("heatmap")).toHaveTextContent("No positions yet");
  });

  it("colors gains green and losses red, stronger with size", () => {
    const rgb = (s: string) => s.match(/\d+/g)!.map(Number);
    const [gr, gg] = rgb(heatColor(3));
    const [rr, rg] = rgb(heatColor(-3));
    expect(gg).toBeGreaterThan(gr);
    expect(rr).toBeGreaterThan(rg);
    expect(rgb(heatColor(5))[1]).toBeGreaterThan(rgb(heatColor(1))[1]);
    expect(heatColor(10)).toBe(heatColor(5));
  });
});
