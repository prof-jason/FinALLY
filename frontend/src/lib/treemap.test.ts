import { describe, expect, it } from "vitest";
import { squarify } from "./treemap";

const overlap = (a: { x: number; y: number; w: number; h: number }, b: typeof a) =>
  a.x < b.x + b.w - 1e-6 && b.x < a.x + a.w - 1e-6 && a.y < b.y + b.h - 1e-6 && b.y < a.y + a.h - 1e-6;

describe("squarify", () => {
  const items = [
    { id: "A", value: 6 },
    { id: "B", value: 6 },
    { id: "C", value: 4 },
    { id: "D", value: 3 },
    { id: "E", value: 2 },
    { id: "F", value: 2 },
    { id: "G", value: 1 },
  ];

  it("gives each item an area proportional to its value and fills the box", () => {
    const rects = squarify(items, 600, 400);
    expect(rects).toHaveLength(items.length);
    const total = items.reduce((a, i) => a + i.value, 0);
    for (const r of rects) {
      expect(r.w * r.h).toBeCloseTo((r.value / total) * 600 * 400, 3);
    }
    const area = rects.reduce((a, r) => a + r.w * r.h, 0);
    expect(area).toBeCloseTo(600 * 400, 3);
  });

  it("keeps rectangles inside the box without overlapping", () => {
    const rects = squarify(items, 300, 500);
    for (const r of rects) {
      expect(r.x).toBeGreaterThanOrEqual(-1e-6);
      expect(r.y).toBeGreaterThanOrEqual(-1e-6);
      expect(r.x + r.w).toBeLessThanOrEqual(300 + 1e-6);
      expect(r.y + r.h).toBeLessThanOrEqual(500 + 1e-6);
    }
    for (let i = 0; i < rects.length; i++)
      for (let j = i + 1; j < rects.length; j++) expect(overlap(rects[i], rects[j])).toBe(false);
  });

  it("produces reasonably square cells", () => {
    const rects = squarify(items, 600, 400);
    const worst = Math.max(...rects.map((r) => Math.max(r.w / r.h, r.h / r.w)));
    expect(worst).toBeLessThan(3);
  });

  it("fills the whole box with a single item", () => {
    expect(squarify([{ id: "A", value: 5 }], 200, 100)).toEqual([
      { id: "A", value: 5, x: 0, y: 0, w: 200, h: 100 },
    ]);
  });

  it("ignores zero/negative values and handles empty input or zero size", () => {
    expect(squarify([], 100, 100)).toEqual([]);
    expect(squarify([{ id: "A", value: 1 }], 0, 100)).toEqual([]);
    expect(squarify([{ id: "A", value: 0 }, { id: "B", value: -3 }], 100, 100)).toEqual([]);
    expect(squarify([{ id: "A", value: 0 }, { id: "B", value: 2 }], 100, 100).map((r) => r.id)).toEqual(["B"]);
  });
});
