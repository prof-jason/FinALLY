import { describe, expect, it } from "vitest";
import { formatPercent, formatPrice, formatQty, formatSignedUsd, formatUsd } from "./format";

describe("format", () => {
  it("formats money, prices, percents and quantities", () => {
    expect(formatUsd(10000)).toBe("$10,000.00");
    expect(formatSignedUsd(12.345)).toBe("+$12.35");
    expect(formatSignedUsd(-5)).toBe("-$5.00");
    expect(formatSignedUsd(0.001)).toBe("$0.00");
    expect(formatPrice(191.234)).toBe("191.23");
    expect(formatPrice(null)).toBe("—");
    expect(formatPercent(0.4212)).toBe("+0.42%");
    expect(formatPercent(-1.5)).toBe("-1.50%");
    expect(formatPercent(0)).toBe("0.00%");
    expect(formatQty(2.5)).toBe("2.5");
    expect(formatQty(10)).toBe("10");
    expect(formatQty(0.123456)).toBe("0.1235");
  });
});
