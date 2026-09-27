"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  CrosshairMode,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { ChartPoint } from "@/lib/types";

type Variant = "sparkline" | "full";

interface Props {
  /** Series, oldest first, strictly increasing integer-second times. May be mutated in place. */
  data: ChartPoint[];
  /** Bump to tell the chart that `data` changed in place. */
  version?: unknown;
  variant?: Variant;
  color: string;
  className?: string;
  /** Show hours:minutes:seconds on the time axis (default true). */
  secondsVisible?: boolean;
}

const toSeries = (p: ChartPoint) => ({ time: p.time as UTCTimestamp, value: p.value });

export default function LineChart({
  data,
  version,
  variant = "full",
  color,
  className,
  secondsVisible = true,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | ISeriesApi<"Area"> | null>(null);
  const drawn = useRef({ count: 0, first: -1 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const spark = variant === "sparkline";
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#7d8896",
        fontSize: 11,
        fontFamily: "var(--font-mono)",
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: !spark, color: "#1b2330" },
        horzLines: { visible: !spark, color: "#1b2330" },
      },
      rightPriceScale: { visible: !spark, borderColor: "#242d3a" },
      leftPriceScale: { visible: false },
      timeScale: {
        visible: !spark,
        borderColor: "#242d3a",
        timeVisible: true,
        secondsVisible,
        rightOffset: spark ? 0 : 4,
        fixLeftEdge: true,
      },
      crosshair: spark
        ? { mode: CrosshairMode.Hidden, vertLine: { visible: false }, horzLine: { visible: false } }
        : { mode: CrosshairMode.Magnet },
      handleScroll: !spark,
      handleScale: !spark,
      localization: { priceFormatter: (p: number) => p.toFixed(2) },
    });
    const series = spark
      ? chart.addSeries(LineSeries, {
          color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        })
      : chart.addSeries(AreaSeries, {
          lineColor: color,
          topColor: `${color}44`,
          bottomColor: `${color}00`,
          lineWidth: 2,
          priceLineVisible: true,
          priceLineColor: color,
        });
    chartRef.current = chart;
    seriesRef.current = series;
    drawn.current = { count: 0, first: -1 };
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [variant, color, secondsVisible]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const d = drawn.current;
    const first = data.length ? data[0].time : -1;
    const grewByAtMostOne = data.length >= d.count && data.length - d.count <= 1;
    if (data.length && d.count && first === d.first && grewByAtMostOne) {
      series.update(toSeries(data[data.length - 1]));
    } else {
      series.setData(data.map(toSeries));
      chartRef.current?.timeScale().fitContent();
    }
    if (variant === "sparkline" && data.length) chartRef.current?.timeScale().fitContent();
    drawn.current = { count: data.length, first };
  }, [data, version, variant, color, secondsVisible]);

  return <div ref={containerRef} className={className} />;
}
