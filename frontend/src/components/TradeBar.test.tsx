import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import TradeBar from "./TradeBar";

const setup = (onTrade = vi.fn().mockResolvedValue({ ok: true, message: "Bought 2.5 AAPL @ 191.23" })) => {
  render(<TradeBar ticker="AAPL" onTickerChange={() => {}} onTrade={onTrade} lastPrice={191.23} />);
  return onTrade;
};

describe("TradeBar", () => {
  it("places fractional buy and sell orders", async () => {
    const onTrade = setup();
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "2.5");
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(onTrade).toHaveBeenCalledWith("AAPL", "buy", 2.5);
    expect(await screen.findByTestId("trade-success")).toHaveTextContent("Bought 2.5 AAPL");
    await userEvent.click(screen.getByTestId("trade-sell-button"));
    expect(onTrade).toHaveBeenLastCalledWith("AAPL", "sell", 2.5);
  });

  it("rejects a zero quantity locally", async () => {
    const onTrade = setup();
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "0");
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent("greater than 0");
  });

  it("shows the server error inline", async () => {
    setup(vi.fn().mockResolvedValue({ ok: false, error: "Insufficient cash" }));
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "1000");
    await userEvent.click(screen.getByTestId("trade-buy-button"));
    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient cash");
  });
});
