"use client";

import { useState, type FormEvent } from "react";
import type { Side } from "@/lib/types";

export type TradeResult = { ok: true; message: string } | { ok: false; error: string };

interface Props {
  ticker: string;
  onTickerChange: (t: string) => void;
  /** Resolves to a confirmation on success or an error message on failure. */
  onTrade: (ticker: string, side: Side, quantity: number) => Promise<TradeResult>;
  lastPrice: number | null;
}

export default function TradeBar({ ticker, onTickerChange, onTrade, lastPrice }: Props) {
  const [qty, setQty] = useState("");
  const [pending, setPending] = useState<Side | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const quantity = Number(qty);
  const estimate = lastPrice != null && quantity > 0 ? lastPrice * quantity : null;

  const submit = async (side: Side) => {
    const t = ticker.trim().toUpperCase();
    setSuccess(null);
    if (!/^[A-Z]{1,5}$/.test(t)) {
      setError("Enter a ticker of 1–5 letters, like AAPL.");
      return;
    }
    if (!qty.trim() || !Number.isFinite(quantity) || quantity <= 0) {
      setError("Enter a quantity greater than 0.");
      return;
    }
    setError(null);
    setPending(side);
    const result = await onTrade(t, side, quantity);
    setPending(null);
    if (result.ok) setSuccess(result.message);
    else setError(result.error);
  };

  // Enter does not place an order: the side must be chosen explicitly.
  const onSubmit = (e: FormEvent) => e.preventDefault();

  return (
    <form onSubmit={onSubmit} className="panel flex flex-wrap items-center gap-2 px-3 py-2" aria-label="Place order">
      <span className="mr-1 text-xs text-muted">Market order</span>
      <input
        data-testid="trade-ticker-input"
        value={ticker}
        onChange={(e) => {
          onTickerChange(e.target.value.toUpperCase());
          setError(null);
        }}
        placeholder="Symbol"
        aria-label="Ticker"
        maxLength={5}
        autoComplete="off"
        spellCheck={false}
        className="field num w-24 uppercase"
      />
      <input
        data-testid="trade-quantity-input"
        value={qty}
        onChange={(e) => {
          setQty(e.target.value);
          setError(null);
        }}
        placeholder="Qty"
        aria-label="Quantity"
        type="number"
        inputMode="decimal"
        min="0"
        step="any"
        className="field num w-28"
      />
      <button
        type="button"
        data-testid="trade-buy-button"
        disabled={pending != null}
        onClick={() => submit("buy")}
        className="btn-buy"
      >
        {pending === "buy" ? "Buying…" : "Buy"}
      </button>
      <button
        type="button"
        data-testid="trade-sell-button"
        disabled={pending != null}
        onClick={() => submit("sell")}
        className="btn-sell"
      >
        {pending === "sell" ? "Selling…" : "Sell"}
      </button>
      <span className="num ml-1 text-xs text-muted">
        {estimate != null ? `≈ ${estimate.toLocaleString("en-US", { style: "currency", currency: "USD" })}` : ""}
      </span>
      <TradeMessage error={error} success={success} />
    </form>
  );
}

function TradeMessage({ error, success }: { error: string | null; success: string | null }) {
  if (error)
    return (
      <span data-testid="trade-error" role="alert" className="ml-auto text-xs text-down">
        {error}
      </span>
    );
  if (success)
    return (
      <span data-testid="trade-success" role="status" className="num ml-auto text-xs text-up">
        {success}
      </span>
    );
  return null;
}
