import { vi } from "vitest";
import type { Portfolio, PriceMap } from "@/lib/types";

export const portfolio = (over: Partial<Portfolio> = {}): Portfolio => ({
  cash_balance: 10000,
  total_value: 10000,
  total_unrealized_pnl: 0,
  positions: [],
  ...over,
});

type Handler = (init: RequestInit | undefined, url: string) => { status?: number; body?: unknown };

/** Install a fetch mock routing "METHOD /path" (query stripped) to handlers. */
export function mockFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    const handler = routes[key];
    if (!handler) return new Response(JSON.stringify({ error: `no mock for ${key}` }), { status: 500 });
    const { status = 200, body } = handler(init, url);
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Minimal controllable EventSource. */
export class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: FakeEventSource[] = [];
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }
  emit(data: PriceMap) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  fail(closed = false) {
    this.readyState = closed ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING;
    this.onerror?.();
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
  static latest() {
    return FakeEventSource.instances[FakeEventSource.instances.length - 1];
  }
}

export const tick = (ticker: string, price: number, previous = price, timestamp = 1_790_000_000): PriceMap => ({
  [ticker]: {
    ticker,
    price,
    previous_price: previous,
    timestamp,
    change: price - previous,
    change_percent: previous ? ((price - previous) / previous) * 100 : 0,
    direction: price > previous ? "up" : price < previous ? "down" : "flat",
  },
});
