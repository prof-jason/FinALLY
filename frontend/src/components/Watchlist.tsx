"use client";

import { memo, useEffect, useState, type FormEvent } from "react";
import LineChart from "./LineChart";
import type { PriceHistory } from "@/hooks/usePriceStream";
import type { ChartPoint } from "@/lib/types";
import { formatPercent, formatPrice } from "@/lib/format";

const EMPTY: ChartPoint[] = [];
const TICKER_RE = /^[A-Z]{1,5}$/;
export const UP = "#2fbf71";
export const DOWN = "#e5534b";

export interface WatchlistRowData {
  ticker: string;
  price: number | null;
  changePercent: number | null;
}

interface RowProps extends WatchlistRowData {
  selected: boolean;
  points: ChartPoint[];
  version: unknown;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

type Flash = { dir: "up" | "down"; n: number } | null;

/** Tracks price changes and returns a short-lived flash direction. */
export function usePriceFlash(price: number | null, holdMs = 250): Flash {
  const [seen, setSeen] = useState(price);
  const [flash, setFlash] = useState<Flash>(null);
  if (price !== seen) {
    setSeen(price);
    if (seen != null && price != null) {
      setFlash({ dir: price > seen ? "up" : "down", n: (flash?.n ?? 0) + 1 });
    }
  }
  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), holdMs);
    return () => clearTimeout(t);
  }, [flash, holdMs]);
  return flash;
}

export const WatchlistRow = memo(function WatchlistRow({
  ticker,
  price,
  changePercent,
  selected,
  points,
  version,
  onSelect,
  onRemove,
}: RowProps) {
  const flash = usePriceFlash(price);
  const tone = changePercent == null ? "flat" : changePercent > 0 ? "up" : changePercent < 0 ? "down" : "flat";
  return (
    <li
      data-testid={`watchlist-row-${ticker}`}
      data-selected={selected ? "true" : "false"}
      className={`wl-row group ${selected ? "wl-row-selected" : ""}`}
    >
      <button
        type="button"
        className="wl-select"
        onClick={() => onSelect(ticker)}
        aria-pressed={selected}
        aria-label={`Show ${ticker} chart`}
      >
        <span className="font-semibold text-text">{ticker}</span>
        <span data-testid={`watchlist-sparkline-${ticker}`} className="h-7 min-w-0">
          <LineChart
            data={points}
            version={version}
            variant="sparkline"
            color={tone === "down" ? DOWN : UP}
            className="h-full w-full"
          />
        </span>
        <span
          data-testid={`watchlist-price-${ticker}`}
          data-flash={flash?.dir}
          className={`num price-cell text-right text-text ${flash ? `flash-${flash.dir}` : ""}`}
        >
          {formatPrice(price)}
        </span>
        <span data-testid={`watchlist-change-${ticker}`} className={`num text-right text-xs tone-${tone}`}>
          {formatPercent(changePercent)}
        </span>
      </button>
      <button
        type="button"
        data-testid={`watchlist-remove-${ticker}`}
        onClick={() => onRemove(ticker)}
        className="wl-remove"
        aria-label={`Remove ${ticker} from watchlist`}
        title={`Remove ${ticker}`}
      >
        ×
      </button>
    </li>
  );
});

interface Props {
  rows: WatchlistRowData[];
  history: PriceHistory;
  version: unknown;
  selected: string | null;
  error: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<boolean>;
  onRemove: (ticker: string) => void;
}

export default function Watchlist({ rows, history, version, selected, error, onSelect, onAdd, onRemove }: Props) {
  const [input, setInput] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (!ticker) return;
    if (!TICKER_RE.test(ticker)) {
      setLocalError("Tickers are 1–5 letters, like AAPL.");
      return;
    }
    setLocalError(null);
    setAdding(true);
    const ok = await onAdd(ticker);
    setAdding(false);
    if (ok) setInput("");
  };

  const shownError = localError ?? error;

  return (
    <section data-testid="watchlist" className="panel flex min-h-0 flex-col" aria-label="Watchlist">
      <div className="panel-head">
        <h2 className="panel-title">Watchlist</h2>
        <span className="num text-xs text-muted">{rows.length}</span>
      </div>
      <form onSubmit={submit} className="flex gap-2 border-b border-line px-3 py-2">
        <input
          data-testid="watchlist-add-input"
          value={input}
          onChange={(e) => {
            setInput(e.target.value.toUpperCase());
            setLocalError(null);
          }}
          placeholder="Add symbol"
          aria-label="Ticker to add"
          maxLength={5}
          autoComplete="off"
          spellCheck={false}
          className="field num min-w-0 flex-1 uppercase"
        />
        <button type="submit" data-testid="watchlist-add-button" disabled={adding} className="btn-blue">
          Add
        </button>
      </form>
      {shownError && (
        <p data-testid="watchlist-error" role="alert" className="border-b border-line px-3 py-1.5 text-xs text-down">
          {shownError}
        </p>
      )}
      <div className="wl-cols text-[11px] text-muted" aria-hidden="true">
        <span>Symbol</span>
        <span />
        <span className="text-right">Last</span>
        <span className="text-right" title="Change since this page started streaming">
          Chg
        </span>
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {rows.map((r) => (
          <WatchlistRow
            key={r.ticker}
            {...r}
            selected={r.ticker === selected}
            points={history.points.get(r.ticker) ?? EMPTY}
            version={version}
            onSelect={onSelect}
            onRemove={onRemove}
          />
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-sm text-muted">Add a symbol above to start watching it.</li>
        )}
      </ul>
    </section>
  );
}
