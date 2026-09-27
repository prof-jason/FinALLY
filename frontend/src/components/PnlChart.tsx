"use client";

import { useMemo } from "react";
import LineChart from "./LineChart";
import type { ChartPoint, Snapshot } from "@/lib/types";
import { formatSignedUsd, pnlTone } from "@/lib/format";

const BLUE = "#209dd7";

/** Snapshots -> strictly increasing per-second chart points (last value wins within a second). */
export function snapshotsToPoints(snapshots: Snapshot[]): ChartPoint[] {
  const out: ChartPoint[] = [];
  for (const s of snapshots) {
    const ms = Date.parse(s.recorded_at);
    if (Number.isNaN(ms)) continue;
    const time = Math.floor(ms / 1000);
    const last = out[out.length - 1];
    if (last && time <= last.time) last.value = s.total_value;
    else out.push({ time, value: s.total_value });
  }
  return out;
}

export default function PnlChart({ snapshots }: { snapshots: Snapshot[] }) {
  const points = useMemo(() => snapshotsToPoints(snapshots), [snapshots]);
  const change = points.length >= 2 ? points[points.length - 1].value - points[0].value : 0;
  return (
    <section
      data-testid="pnl-chart"
      data-points={points.length}
      className="panel flex min-h-0 flex-col"
      aria-label="Portfolio value over time"
    >
      <div className="panel-head">
        <h2 className="panel-title">Portfolio value</h2>
        <span className={`num text-xs tone-${pnlTone(change)}`}>
          {points.length >= 2 ? `${formatSignedUsd(change)} over period` : ""}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        <LineChart
          data={points}
          color={BLUE}
          secondsVisible={false}
          className={`absolute inset-0 ${points.length < 2 ? "invisible" : ""}`}
        />
        {points.length < 2 && (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-muted">
            Value is recorded every 30 seconds and after each trade.
          </p>
        )}
      </div>
    </section>
  );
}
