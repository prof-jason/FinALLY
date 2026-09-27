import type {
  ChatResponse,
  Portfolio,
  Side,
  Snapshot,
  Trade,
  TradeResponse,
  WatchlistItem,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running.", 0);
  }
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // non-JSON body; handled below
  }
  if (!res.ok) {
    const msg =
      body && typeof body === "object" && "error" in body && typeof body.error === "string"
        ? body.error
        : `Request failed (${res.status})`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  getPortfolio: () => request<Portfolio>("/api/portfolio"),
  trade: (ticker: string, side: Side, quantity: number) =>
    request<TradeResponse>("/api/portfolio/trade", post({ ticker, side, quantity })),
  getHistory: () =>
    request<{ snapshots: Snapshot[] }>("/api/portfolio/history").then((r) => r.snapshots),
  getTrades: (limit = 100) =>
    request<{ trades: Trade[] }>(`/api/portfolio/trades?limit=${limit}`).then((r) => r.trades),
  reset: () => request<Portfolio>("/api/portfolio/reset", { method: "POST" }),
  getWatchlist: () =>
    request<{ watchlist: WatchlistItem[] }>("/api/watchlist").then((r) => r.watchlist),
  addWatchlist: (ticker: string) => request<WatchlistItem>("/api/watchlist", post({ ticker })),
  removeWatchlist: (ticker: string) =>
    request<void>(`/api/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" }),
  chat: (message: string) => request<ChatResponse>("/api/chat", post({ message })),
};
