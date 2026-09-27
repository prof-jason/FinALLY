"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api } from "@/lib/api";
import type { ChatActions, ChatResponse } from "@/lib/types";
import { formatPrice, formatQty } from "@/lib/format";

export interface ChatEntry {
  id: number;
  role: "user" | "assistant" | "error";
  content: string;
  actions?: ChatActions | null;
}

interface Props {
  open: boolean;
  onToggle: () => void;
  /** Called after every successful reply, so the terminal can refresh state. */
  onResponse: (res: ChatResponse) => void;
}

const SUGGESTIONS = [
  "How is my portfolio doing?",
  "Buy 5 AAPL",
  "Add PYPL to my watchlist",
];

export function ActionList({ actions }: { actions: ChatActions }) {
  const items = [
    ...(actions.watchlist_changes ?? []).map((w, i) => {
      const verb = w.action === "add" ? "Added" : "Removed";
      const want = w.action === "add" ? "Add" : "Remove";
      const ok = w.status === "executed";
      return (
        <li key={`w${i}`} data-testid="chat-action" data-status={w.status} data-kind="watchlist" className={`chat-action ${ok ? "ok" : "fail"}`}>
          <span className="font-semibold">{ok ? `${verb} ${w.ticker}` : `${want} ${w.ticker} failed`}</span>
          <span className="text-muted"> {ok ? (w.action === "add" ? "to watchlist" : "from watchlist") : `: ${w.error ?? "unknown error"}`}</span>
        </li>
      );
    }),
    ...(actions.trades ?? []).map((t, i) => {
      const ok = t.status === "executed";
      const verb = t.side === "buy" ? (ok ? "Bought" : "Buy") : ok ? "Sold" : "Sell";
      return (
        <li key={`t${i}`} data-testid="chat-action" data-status={t.status} data-kind="trade" className={`chat-action ${ok ? "ok" : "fail"}`}>
          <span className="num font-semibold">
            {verb} {formatQty(t.quantity)} {t.ticker}
            {ok && t.price != null ? ` @ ${formatPrice(t.price)}` : ""}
          </span>
          {!ok && <span className="text-muted"> failed: {t.error ?? "unknown error"}</span>}
        </li>
      );
    }),
  ];
  if (!items.length) return null;
  return <ul className="mt-2 flex flex-col gap-1">{items}</ul>;
}

export default function ChatPanel({ open, onToggle, onResponse }: Props) {
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const nextId = useRef(1);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  const push = (e: Omit<ChatEntry, "id">) =>
    setMessages((m) => [...m, { ...e, id: nextId.current++ }]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || loading) return;
    setInput("");
    push({ role: "user", content: message });
    setLoading(true);
    try {
      const res = await api.chat(message);
      push({ role: "assistant", content: res.message, actions: res.actions });
      onResponse(res);
    } catch (err) {
      push({ role: "error", content: err instanceof Error ? err.message : "The assistant didn't respond." });
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  };

  return (
    <aside
      data-testid="chat-panel"
      data-open={open ? "true" : "false"}
      className={`panel flex min-h-0 flex-col ${open ? "" : "chat-collapsed"}`}
      aria-label="AI assistant"
    >
      <div className="panel-head">
        {open && (
          <h2 className="panel-title">
            Ask <span className="text-accent">FinAlly</span>
          </h2>
        )}
        <button
          type="button"
          data-testid="chat-toggle"
          onClick={onToggle}
          className="btn-icon"
          aria-expanded={open}
          aria-label={open ? "Collapse assistant" : "Expand assistant"}
          title={open ? "Collapse assistant" : "Expand assistant"}
        >
          {open ? "›" : "‹"}
        </button>
      </div>

      {open ? (
        <>
          <div ref={scroller} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3" aria-live="polite">
            {messages.length === 0 && !loading && (
              <div className="space-y-3 text-sm text-muted">
                <p>
                  Ask about your holdings, risk, or P&amp;L. FinAlly can place market orders and edit your watchlist
                  for you.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" className="chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) =>
              m.role === "error" ? (
                <div key={m.id} data-testid="chat-error" role="alert" className="chat-bubble chat-error">
                  {m.content}
                </div>
              ) : (
                <div
                  key={m.id}
                  data-testid="chat-message"
                  data-role={m.role}
                  className={`chat-bubble ${m.role === "user" ? "chat-user" : "chat-assistant"}`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.actions && <ActionList actions={m.actions} />}
                </div>
              ),
            )}
            {loading && (
              <div data-testid="chat-loading" role="status" className="chat-bubble chat-assistant chat-loading">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
                <span className="sr-only">FinAlly is thinking</span>
              </div>
            )}
          </div>
          <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-line p-2">
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Message FinAlly"
              aria-label="Message FinAlly"
              className="field min-h-0 flex-1 resize-none"
            />
            <button type="submit" data-testid="chat-send" disabled={loading || !input.trim()} className="btn-purple">
              Send
            </button>
          </form>
        </>
      ) : null}
    </aside>
  );
}
