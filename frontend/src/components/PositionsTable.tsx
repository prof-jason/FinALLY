"use client";

import type { Position } from "@/lib/types";
import { formatPercent, formatPrice, formatQty, formatSignedUsd, pnlTone } from "@/lib/format";

interface Props {
  positions: Position[];
  onSelect: (ticker: string) => void;
}

export default function PositionsTable({ positions, onSelect }: Props) {
  return (
    <section className="panel flex min-h-0 flex-col" aria-label="Positions">
      <div className="panel-head">
        <h2 className="panel-title">Positions</h2>
        <span className="num text-xs text-muted">{positions.length}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table data-testid="positions-table" className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Qty</th>
              <th>Avg cost</th>
              <th>Last</th>
              <th>Unrealized P&amp;L</th>
              <th>%</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const tone = pnlTone(p.unrealized_pnl);
              return (
                <tr
                  key={p.ticker}
                  data-testid={`position-row-${p.ticker}`}
                  onClick={() => onSelect(p.ticker)}
                  className="cursor-pointer"
                >
                  <td className="font-semibold text-text">{p.ticker}</td>
                  <td data-testid={`position-qty-${p.ticker}`}>{formatQty(p.quantity)}</td>
                  <td>{formatPrice(p.avg_cost)}</td>
                  <td className="text-text">{formatPrice(p.current_price)}</td>
                  <td className={`tone-${tone}`}>{formatSignedUsd(p.unrealized_pnl)}</td>
                  <td className={`tone-${tone}`}>{formatPercent(p.unrealized_pnl_percent)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {positions.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-muted">No open positions.</p>
        )}
      </div>
    </section>
  );
}
