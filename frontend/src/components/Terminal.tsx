"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Header from "./Header";
import Watchlist, { type WatchlistRowData } from "./Watchlist";
import MainChart from "./MainChart";
import TradeBar, { type TradeResult } from "./TradeBar";
import Heatmap from "./Heatmap";
import PnlChart from "./PnlChart";
import PositionsTable from "./PositionsTable";
import TradeHistory from "./TradeHistory";
import ChatPanel from "./ChatPanel";
import { usePriceStream } from "@/hooks/usePriceStream";
import { api, ApiError } from "@/lib/api";
import { computeLivePortfolio } from "@/lib/portfolio";
import { formatPrice, formatQty } from "@/lib/format";
import type { ChartPoint, ChatResponse, Portfolio, Side, Snapshot, Trade, WatchlistItem } from "@/lib/types";

const EMPTY: ChartPoint[] = [];
const errMsg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");

export default function Terminal() {
  const { prices, status, history } = usePriceStream();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tradeTicker, setTradeTicker] = useState("");
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [resetCount, setResetCount] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshActivity = useCallback(async () => {
    const [t, s] = await Promise.all([api.getTrades(), api.getHistory()]);
    setTrades(t);
    setSnapshots(s);
  }, []);

  const refreshWatchlist = useCallback(async () => {
    const w = await api.getWatchlist();
    setWatchlist(w);
    return w;
  }, []);

  const refreshAll = useCallback(async () => {
    const [p] = await Promise.all([api.getPortfolio(), refreshWatchlist(), refreshActivity()]);
    setPortfolio(p);
  }, [refreshActivity, refreshWatchlist]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getPortfolio(), api.getWatchlist(), api.getTrades(), api.getHistory()])
      .then(([p, w, t, s]) => {
        if (cancelled) return;
        setPortfolio(p);
        setWatchlist(w);
        setTrades(t);
        setSnapshots(s);
        setLoadError(null);
        setSelected((cur) => cur ?? w[0]?.ticker ?? null);
        setTradeTicker((cur) => cur || (w[0]?.ticker ?? ""));
      })
      .catch((e) => {
        if (!cancelled) setLoadError(errMsg(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The P&L chart gains a snapshot every 30s on the server.
  useEffect(() => {
    const t = setInterval(() => {
      api.getHistory().then(setSnapshots).catch(() => {});
    }, 30_000);
    return () => clearInterval(t);
  }, []);

  const live = useMemo(() => computeLivePortfolio(portfolio, prices), [portfolio, prices]);

  const rows: WatchlistRowData[] = useMemo(
    () =>
      watchlist.map((w) => {
        const price = prices[w.ticker]?.price ?? w.price;
        const open = history.open.get(w.ticker) ?? w.price;
        return {
          ticker: w.ticker,
          price,
          changePercent: price != null && open ? ((price - open) / open) * 100 : null,
        };
      }),
    [watchlist, prices, history],
  );

  const select = useCallback((ticker: string) => {
    setSelected(ticker);
    setTradeTicker(ticker);
  }, []);

  const addTicker = useCallback(async (ticker: string) => {
    setWatchlistError(null);
    try {
      const item = await api.addWatchlist(ticker);
      setWatchlist((w) => (w.some((x) => x.ticker === item.ticker) ? w : [...w, item]));
      setSelected(item.ticker);
      return true;
    } catch (e) {
      setWatchlistError(errMsg(e));
      return false;
    }
  }, []);

  const removeTicker = useCallback(async (ticker: string) => {
    setWatchlistError(null);
    try {
      await api.removeWatchlist(ticker);
      setWatchlist((w) => {
        const next = w.filter((x) => x.ticker !== ticker);
        setSelected((cur) => (cur === ticker ? (next[0]?.ticker ?? null) : cur));
        return next;
      });
    } catch (e) {
      setWatchlistError(errMsg(e));
    }
  }, []);

  const placeTrade = useCallback(
    async (ticker: string, side: Side, quantity: number): Promise<TradeResult> => {
      try {
        const res = await api.trade(ticker, side, quantity);
        setPortfolio(res.portfolio);
        refreshActivity().catch(() => {});
        const t = res.trade;
        return {
          ok: true,
          message: `${t.side === "buy" ? "Bought" : "Sold"} ${formatQty(t.quantity)} ${t.ticker} @ ${formatPrice(t.price)}`,
        };
      } catch (e) {
        return { ok: false, error: errMsg(e) };
      }
    },
    [refreshActivity],
  );

  const onChatResponse = useCallback(
    (res: ChatResponse) => {
      const a = res.actions;
      if (!a || (!a.trades?.length && !a.watchlist_changes?.length)) return;
      refreshAll().catch(() => {});
    },
    [refreshAll],
  );

  const reset = useCallback(async () => {
    setResetting(true);
    try {
      const p = await api.reset();
      setPortfolio(p);
      const w = await refreshWatchlist();
      await refreshActivity();
      setSelected(w[0]?.ticker ?? null);
      setTradeTicker(w[0]?.ticker ?? "");
      setWatchlistError(null);
      setResetCount((n) => n + 1);
    } catch (e) {
      setLoadError(errMsg(e));
    } finally {
      setResetting(false);
    }
  }, [refreshActivity, refreshWatchlist]);

  const selectedPrice = selected ? (rows.find((r) => r.ticker === selected) ?? null) : null;
  const tradePrice = prices[tradeTicker]?.price ?? null;

  return (
    <div className="terminal-shell">
      <Header
        totalValue={live.totalValue}
        cash={live.cash}
        pnl={live.totalPnl}
        status={status}
        resetting={resetting}
        onReset={reset}
        loaded={portfolio != null}
      />
      {loadError && (
        <p role="alert" className="border-b border-line bg-panel px-4 py-1.5 text-xs text-down">
          {loadError}
        </p>
      )}
      <main className={`terminal-grid ${chatOpen ? "" : "chat-closed"}`}>
        <div className="area-watchlist min-h-0">
          <Watchlist
            rows={rows}
            history={history}
            version={prices}
            selected={selected}
            error={watchlistError}
            onSelect={select}
            onAdd={addTicker}
            onRemove={removeTicker}
          />
        </div>
        <div className="area-center">
          <div className="area-chart min-h-0">
            <MainChart
              ticker={selected}
              points={(selected && history.points.get(selected)) || EMPTY}
              version={prices}
              price={selectedPrice?.price ?? null}
              changePercent={selectedPrice?.changePercent ?? null}
            />
          </div>
          <div className="area-trade">
            <TradeBar ticker={tradeTicker} onTickerChange={setTradeTicker} onTrade={placeTrade} lastPrice={tradePrice} />
          </div>
          <div className="area-heat min-h-0">
            <Heatmap positions={live.positions} />
          </div>
          <div className="area-pnl min-h-0">
            <PnlChart snapshots={snapshots} />
          </div>
          <div className="area-positions min-h-0">
            <PositionsTable positions={live.positions} onSelect={select} />
          </div>
          <div className="area-history min-h-0">
            <TradeHistory trades={trades} />
          </div>
        </div>
        <div className="area-chat min-h-0">
          <ChatPanel
            key={resetCount}
            open={chatOpen}
            onToggle={() => setChatOpen((o) => !o)}
            onResponse={onChatResponse}
          />
        </div>
      </main>
    </div>
  );
}
