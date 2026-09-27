"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Position } from "@/lib/types";
import { squarify } from "@/lib/treemap";
import { formatPercent, formatUsd } from "@/lib/format";

interface Props {
  positions: Position[];
  /** Fixed size (tests); otherwise the container is measured. */
  size?: { width: number; height: number };
}

/** Green/red fill whose strength follows the P&L percentage, saturating at ±5%. */
export function heatColor(pnlPercent: number): string {
  const t = Math.min(Math.abs(pnlPercent) / 5, 1);
  if (Math.abs(pnlPercent) < 0.005) return "rgb(40, 48, 60)";
  const [r, g, b] = pnlPercent > 0 ? [31, 138, 84] : [178, 53, 48];
  const base = [30, 38, 50];
  const mix = (a: number, c: number) => Math.round(a + (c - a) * (0.35 + 0.65 * t));
  return `rgb(${mix(base[0], r)}, ${mix(base[1], g)}, ${mix(base[2], b)})`;
}

function useSize(ref: React.RefObject<HTMLDivElement | null>, fixed?: Props["size"]) {
  const [size, setSize] = useState(fixed ?? { width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (fixed || !el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fixed]);
  return fixed ?? size;
}

export default function Heatmap({ positions, size: fixedSize }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const { width, height } = useSize(ref, fixedSize);
  const total = positions.reduce((a, p) => a + Math.max(p.market_value, 0), 0);

  const rects = useMemo(
    () =>
      squarify(
        positions.map((p) => ({ id: p.ticker, value: p.market_value, data: p })),
        width,
        height,
      ),
    [positions, width, height],
  );

  return (
    <section className="panel flex min-h-0 flex-col" aria-label="Portfolio heatmap">
      <div className="panel-head">
        <h2 className="panel-title">Holdings map</h2>
        <span className="text-xs text-muted">Size by weight, color by P&amp;L</span>
      </div>
      <div ref={ref} data-testid="heatmap" className="relative min-h-0 flex-1 overflow-hidden">
        {positions.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-muted">
            No positions yet. Buy shares to see them here.
          </p>
        )}
        {rects.map((r) => {
          const p = r.data!;
          const pct = p.unrealized_pnl_percent;
          const tone = pct > 0.005 ? "positive" : pct < -0.005 ? "negative" : "flat";
          const small = r.w < 64 || r.h < 40;
          return (
            <div
              key={r.id}
              data-testid={`heatmap-cell-${r.id}`}
              data-pnl={tone}
              title={`${p.ticker}: ${formatUsd(p.market_value)} (${((p.market_value / total) * 100).toFixed(1)}%), P&L ${formatPercent(pct)}`}
              className="heat-cell"
              style={{
                left: r.x,
                top: r.y,
                width: r.w,
                height: r.h,
                backgroundColor: heatColor(pct),
              }}
            >
              <span className="font-semibold">{p.ticker}</span>
              {!small && <span className="num text-xs opacity-90">{formatPercent(pct)}</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
