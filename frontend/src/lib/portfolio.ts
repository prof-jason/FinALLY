import type { Portfolio, Position, PriceMap } from "./types";

export interface LivePortfolio {
  cash: number;
  totalValue: number;
  totalPnl: number;
  positions: Position[];
}

/**
 * Revalue a portfolio snapshot from the latest streamed prices.
 * Positions without a streamed price keep the server's `current_price`.
 */
export function computeLivePortfolio(portfolio: Portfolio | null, prices: PriceMap): LivePortfolio {
  if (!portfolio) return { cash: 0, totalValue: 0, totalPnl: 0, positions: [] };
  let marketValue = 0;
  let totalPnl = 0;
  const positions = portfolio.positions.map((p) => {
    const price = prices[p.ticker]?.price ?? p.current_price;
    const value = price * p.quantity;
    const cost = p.avg_cost * p.quantity;
    const pnl = value - cost;
    marketValue += value;
    totalPnl += pnl;
    return {
      ...p,
      current_price: price,
      market_value: value,
      unrealized_pnl: pnl,
      unrealized_pnl_percent: cost > 0 ? (pnl / cost) * 100 : 0,
    };
  });
  return {
    cash: portfolio.cash_balance,
    totalValue: portfolio.cash_balance + marketValue,
    totalPnl,
    positions,
  };
}
