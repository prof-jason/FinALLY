"use client";

import type { Trade } from "@/lib/types";
import { formatDateTime, formatPrice, formatQty } from "@/lib/format";

export default function TradeHistory({ trades }: { trades: Trade[] }) {
  return (
    <section className="panel flex min-h-0 flex-col" aria-label="Trade history">
      <div className="panel-head">
        <h2 className="panel-title">Trade history</h2>
        <span className="num text-xs text-muted">{trades.length}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table data-testid="trade-history" className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Qty</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} data-testid="trade-history-row" data-ticker={t.ticker} data-side={t.side}>
                <td className="text-muted">{formatDateTime(t.executed_at)}</td>
                <td className="font-semibold text-text">{t.ticker}</td>
                <td className={t.side === "buy" ? "text-up" : "text-down"}>{t.side === "buy" ? "Buy" : "Sell"}</td>
                <td>{formatQty(t.quantity)}</td>
                <td>{formatPrice(t.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {trades.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">No trades yet.</p>}
      </div>
    </section>
  );
}
