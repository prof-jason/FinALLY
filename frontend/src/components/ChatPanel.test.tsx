import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ChatPanel from "./ChatPanel";
import { mockFetch } from "@/test/mocks";

afterEach(() => vi.unstubAllGlobals());

describe("ChatPanel", () => {
  it("shows a loading indicator, then the reply with inline action results", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const reply = {
      message: "Placing an order for 10 AAPL.",
      actions: {
        trades: [
          { ticker: "AAPL", side: "buy", quantity: 10, status: "executed", price: 191.23 },
          { ticker: "TSLA", side: "buy", quantity: 500, status: "failed", error: "Insufficient cash" },
        ],
        watchlist_changes: [{ ticker: "PYPL", action: "add", status: "executed" }],
      },
    };
    const fetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      expect([String(url), init?.method]).toEqual(["/api/chat", "POST"]);
      await gate;
      return new Response(JSON.stringify(reply), { status: 200 });
    });
    vi.stubGlobal("fetch", fetch);
    const onResponse = vi.fn();
    render(<ChatPanel open onToggle={() => {}} onResponse={onResponse} />);

    await userEvent.type(screen.getByTestId("chat-input"), "buy 10 AAPL{Enter}");
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send")).toBeDisabled();
    const [user] = screen.getAllByTestId("chat-message");
    expect(user).toHaveAttribute("data-role", "user");
    expect(user).toHaveTextContent("buy 10 AAPL");

    release();
    await waitFor(() => expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument());
    const assistant = screen.getAllByTestId("chat-message")[1];
    expect(assistant).toHaveAttribute("data-role", "assistant");
    expect(assistant).toHaveTextContent("Placing an order for 10 AAPL.");

    const actions = screen.getAllByTestId("chat-action");
    expect(actions.map((a) => a.getAttribute("data-status"))).toEqual(["executed", "executed", "failed"]);
    expect(actions[0]).toHaveTextContent("Added PYPL");
    expect(actions[1]).toHaveTextContent("Bought 10 AAPL @ 191.23");
    expect(actions[2]).toHaveTextContent("Insufficient cash");
    expect(onResponse).toHaveBeenCalledWith(reply);
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ message: "buy 10 AAPL" });
  });

  it("shows the server error when the assistant is unavailable", async () => {
    mockFetch({
      "POST /api/chat": () => ({ status: 503, body: { error: "The AI assistant is unavailable right now, please try again shortly." } }),
    });
    const onResponse = vi.fn();
    render(<ChatPanel open onToggle={() => {}} onResponse={onResponse} />);
    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send"));
    expect(await screen.findByTestId("chat-error")).toHaveTextContent("unavailable right now");
    expect(onResponse).not.toHaveBeenCalled();
  });

  it("collapses to a toggle button", async () => {
    const onToggle = vi.fn();
    render(<ChatPanel open={false} onToggle={onToggle} onResponse={() => {}} />);
    expect(screen.getByTestId("chat-panel")).toHaveAttribute("data-open", "false");
    expect(screen.queryByTestId("chat-input")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("chat-toggle"));
    expect(onToggle).toHaveBeenCalled();
  });
});
