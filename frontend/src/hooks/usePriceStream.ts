"use client";

import { useEffect, useState } from "react";
import type { ChartPoint, ConnectionStatus, PriceMap, PriceUpdate } from "@/lib/types";

const MAX_POINTS = 3600; // one point per second, ~1 hour per ticker
const RECONNECT_MS = 3000;

export interface PriceHistory {
  /** Per-ticker price series since page load, one point per second. */
  points: Map<string, ChartPoint[]>;
  /** First price seen for each ticker this session (baseline for change %). */
  open: Map<string, number>;
}

/** Append a price to a per-second series, replacing the last point if it shares the second. */
export function appendPoint(series: ChartPoint[], update: PriceUpdate, max = MAX_POINTS): void {
  const time = Math.floor(update.timestamp);
  const last = series[series.length - 1];
  if (last && time <= last.time) {
    last.value = update.price;
    return;
  }
  series.push({ time, value: update.price });
  if (series.length > max) series.splice(0, series.length - max);
}

export function usePriceStream(url = "/api/stream/prices") {
  const [prices, setPrices] = useState<PriceMap>({});
  const [status, setStatus] = useState<ConnectionStatus>("reconnecting");
  // Mutable, identity-stable store; `prices` state changes drive re-renders.
  const [history] = useState<PriceHistory>(() => ({ points: new Map(), open: new Map() }));

  useEffect(() => {
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      es = new EventSource(url);
      es.onopen = () => setStatus("connected");
      es.onmessage = (ev) => {
        let data: PriceMap;
        try {
          data = JSON.parse(ev.data);
        } catch {
          return;
        }
        const h = history;
        for (const u of Object.values(data)) {
          if (!u || typeof u.price !== "number") continue;
          if (!h.open.has(u.ticker)) h.open.set(u.ticker, u.price);
          let series = h.points.get(u.ticker);
          if (!series) h.points.set(u.ticker, (series = []));
          appendPoint(series, u);
        }
        setStatus("connected");
        setPrices((prev) => ({ ...prev, ...data }));
      };
      es.onerror = () => {
        if (!es) return;
        if (es.readyState === EventSource.CLOSED) {
          // The browser gave up; retry ourselves.
          setStatus("disconnected");
          es.close();
          if (!closed) retry = setTimeout(connect, RECONNECT_MS);
        } else {
          setStatus("reconnecting");
        }
      };
    };

    // An open stream can sit silently through a network drop, so follow the browser's
    // own connectivity events: drop to "disconnected" at once, reconnect when back.
    const onOffline = () => {
      if (retry) clearTimeout(retry);
      es?.close();
      setStatus("disconnected");
    };
    const onOnline = () => {
      if (retry) clearTimeout(retry);
      es?.close();
      setStatus("reconnecting");
      connect();
    };

    connect();
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      closed = true;
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      if (retry) clearTimeout(retry);
      es?.close();
    };
  }, [url, history]);

  return { prices, status, history };
}
