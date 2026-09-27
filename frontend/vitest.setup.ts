import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());
import { vi } from "vitest";

// Lightweight Charts draws to canvas, which jsdom lacks. Tests only need the API surface.
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), update: vi.fn() });
  return {
    createChart: vi.fn(() => ({
      addSeries: vi.fn(series),
      remove: vi.fn(),
      timeScale: () => ({ fitContent: vi.fn() }),
    })),
    LineSeries: "Line",
    AreaSeries: "Area",
    ColorType: { Solid: "solid" },
    CrosshairMode: { Normal: 0, Magnet: 1, Hidden: 2 },
  };
});
