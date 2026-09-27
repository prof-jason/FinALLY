"use client";

import LineChart from "./LineChart";
import { DOWN, UP } from "./Watchlist";
import type { ChartPoint } from "@/lib/types";
import { formatPercent, formatPrice } from "@/lib/format";

interface Props {
  ticker: string | null;
  points: ChartPoint[];
  version: unknown;
  price: number | null;
  changePercent: number | null;
}

export default function MainChart({ ticker, points, version, price, changePercent }: Props) {
  const down = (changePercent ?? 0) < 0;
  return (
    <section
      data-testid="main-chart"
      data-ticker={ticker ?? ""}
      className="panel flex min-h-0 flex-col"
      aria-label="Price chart"
    >
      <div className="panel-head">
        <div className="flex items-baseline gap-3">
          <h2 data-testid="main-chart-ticker" className="text-base font-semibold text-text">
            {ticker ?? "No symbol"}
          </h2>
          <span className="num text-base text-text">{formatPrice(price)}</span>
          <span className={`num text-xs tone-${down ? "down" : changePercent ? "up" : "flat"}`}>
            {formatPercent(changePercent)}
          </span>
        </div>
        <span className="text-xs text-muted">Since page load</span>
      </div>
      <div className="relative min-h-0 flex-1">
        {ticker ? (
          <LineChart
            key={ticker}
            data={points}
            version={version}
            color={down ? DOWN : UP}
            className="absolute inset-0"
          />
        ) : null}
        {(!ticker || points.length < 2) && (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted">
            {ticker ? `Collecting ${ticker} prices…` : "Select a symbol in the watchlist to chart it."}
          </p>
        )}
      </div>
    </section>
  );
}
