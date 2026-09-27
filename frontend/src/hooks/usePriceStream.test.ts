import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { appendPoint, usePriceStream } from "./usePriceStream";
import { FakeEventSource, tick } from "@/test/mocks";
import type { ChartPoint } from "@/lib/types";

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("appendPoint", () => {
  it("buckets updates to one point per second and caps length", () => {
    const s: ChartPoint[] = [];
    appendPoint(s, tick("A", 1, 1, 100.1).A);
    appendPoint(s, tick("A", 2, 1, 100.6).A);
    appendPoint(s, tick("A", 3, 2, 101.2).A);
    expect(s).toEqual([
      { time: 100, value: 2 },
      { time: 101, value: 3 },
    ]);
    for (let i = 0; i < 5; i++) appendPoint(s, tick("A", i, i, 200 + i).A, 3);
    expect(s.map((p) => p.time)).toEqual([202, 203, 204]);
  });
});

describe("usePriceStream", () => {
  it("tracks connection status and accumulates prices and history", () => {
    const { result } = renderHook(() => usePriceStream());
    expect(result.current.status).toBe("reconnecting");
    const es = FakeEventSource.latest();
    expect(es.url).toBe("/api/stream/prices");

    act(() => es.open());
    expect(result.current.status).toBe("connected");

    act(() => es.emit({ ...tick("AAPL", 190, 190, 1000), ...tick("MSFT", 400, 400, 1000) }));
    act(() => es.emit(tick("AAPL", 191, 190, 1001)));
    expect(result.current.prices.AAPL.price).toBe(191);
    expect(result.current.prices.MSFT.price).toBe(400);
    expect(result.current.history.points.get("AAPL")).toEqual([
      { time: 1000, value: 190 },
      { time: 1001, value: 191 },
    ]);
    expect(result.current.history.open.get("AAPL")).toBe(190);

    act(() => es.fail(false));
    expect(result.current.status).toBe("reconnecting");
  });

  it("reconnects itself after the browser closes the stream", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePriceStream());
    act(() => FakeEventSource.latest().fail(true));
    expect(result.current.status).toBe("disconnected");
    act(() => vi.advanceTimersByTime(3000));
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => FakeEventSource.latest().open());
    expect(result.current.status).toBe("connected");
  });

  it("follows browser offline/online events", () => {
    const { result } = renderHook(() => usePriceStream());
    act(() => FakeEventSource.latest().open());
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(result.current.status).toBe("disconnected");
    expect(FakeEventSource.latest().readyState).toBe(FakeEventSource.CLOSED);
    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(result.current.status).toBe("reconnecting");
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => FakeEventSource.latest().open());
    expect(result.current.status).toBe("connected");
  });
});
