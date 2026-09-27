// Shapes from planning/TEAM_CONTRACTS.md ("HTTP API shapes").

export type Direction = "up" | "down" | "flat";
export type Side = "buy" | "sell";

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number; // unix seconds
  change: number;
  change_percent: number;
  direction: Direction;
}

export type PriceMap = Record<string, PriceUpdate>;

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  total_value: number;
  total_unrealized_pnl: number;
  positions: Position[];
}

export interface Trade {
  id: string;
  ticker: string;
  side: Side;
  quantity: number;
  price: number;
  executed_at: string;
}

export interface TradeResponse {
  trade: Trade;
  portfolio: Portfolio;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change: number | null;
  change_percent: number | null;
  direction: Direction | null;
  added_at: string;
}

export type ActionStatus = "executed" | "failed";

export interface ChatTradeAction {
  ticker: string;
  side: Side;
  quantity: number;
  status: ActionStatus;
  price?: number | null;
  error?: string | null;
}

export interface ChatWatchlistAction {
  ticker: string;
  action: "add" | "remove";
  status: ActionStatus;
  error?: string | null;
}

export interface ChatActions {
  trades: ChatTradeAction[];
  watchlist_changes: ChatWatchlistAction[];
}

export interface ChatResponse {
  message: string;
  actions: ChatActions | null;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

export interface ChartPoint {
  time: number; // unix seconds (integer)
  value: number;
}
