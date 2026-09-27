"use client";

import type { ConnectionStatus } from "@/lib/types";
import { formatSignedUsd, formatUsd, pnlTone } from "@/lib/format";

interface Props {
  totalValue: number;
  cash: number;
  pnl: number;
  status: ConnectionStatus;
  resetting: boolean;
  onReset: () => void;
  loaded: boolean;
}

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  connected: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

export default function Header({ totalValue, cash, pnl, status, resetting, onReset, loaded }: Props) {
  const tone = pnlTone(pnl);
  return (
    <header className="flex flex-wrap items-center gap-x-8 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-semibold tracking-tight text-text">
          Fin<span className="text-accent">Ally</span>
        </span>
        <span className="hidden text-xs text-muted sm:inline">AI trading workstation</span>
      </div>

      <div className="flex items-baseline gap-3">
        <span className="text-xs text-muted">Portfolio</span>
        <span
          data-testid="header-total-value"
          className="num text-2xl font-semibold text-accent"
        >
          {loaded ? formatUsd(totalValue) : "—"}
        </span>
        <span className="text-xs text-muted">Unrealized</span>
        <span data-testid="header-pnl" className={`num text-sm tone-${tone}`}>
          {loaded ? formatSignedUsd(pnl) : ""}
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-xs text-muted">Cash</span>
        <span data-testid="header-cash" className="num text-base text-text">
          {loaded ? formatUsd(cash) : "—"}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="flex items-center gap-2 text-xs text-muted" title={`Price stream: ${STATUS_LABEL[status]}`}>
          <span
            data-testid="connection-status"
            data-status={status}
            aria-label={`Price stream ${STATUS_LABEL[status]}`}
            className={`status-dot status-${status}`}
          />
          {STATUS_LABEL[status]}
        </div>
        <button
          type="button"
          data-testid="reset-button"
          onClick={onReset}
          disabled={resetting}
          className="btn-ghost"
          title="Restore $10,000 cash, clear positions, trades and chat, and restore the default watchlist"
        >
          {resetting ? "Resetting…" : "Reset"}
        </button>
      </div>
    </header>
  );
}
