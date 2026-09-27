const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatUsd(n: number): string {
  return usd.format(n);
}

/** `+$12.34` / `-$5.00` / `$0.00` */
export function formatSignedUsd(n: number): string {
  if (Math.abs(n) < 0.005) return usd.format(0);
  return (n > 0 ? "+" : "-") + usd.format(Math.abs(n));
}

export function formatPrice(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(2);
}

export function formatPercent(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const v = Math.abs(n) < 0.005 ? 0 : n;
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/** Up to 4 decimals, trailing zeros trimmed: 2.5 -> "2.5", 10 -> "10". */
export function formatQty(n: number): string {
  return Number(n.toFixed(4)).toString();
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-US", { hour12: false });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `${date} ${d.toLocaleTimeString("en-US", { hour12: false })}`;
}

export function pnlTone(n: number): "up" | "down" | "flat" {
  if (n > 0.005) return "up";
  if (n < -0.005) return "down";
  return "flat";
}
