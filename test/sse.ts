/**
 * Minimal SSE reader for API-level specs: connects to the price stream,
 * collects `data:` events until `predicate` holds or the timeout expires.
 */
export type PriceEvent = Record<
  string,
  { ticker: string; price: number; previous_price: number; timestamp: number | string; direction: string }
>;

export async function collectPriceEvents(
  baseURL: string,
  predicate: (events: PriceEvent[]) => boolean,
  timeoutMs = 10_000,
): Promise<{ events: PriceEvent[]; contentType: string | null }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const events: PriceEvent[] = [];
  let contentType: string | null = null;
  try {
    const res = await fetch(new URL("/api/stream/prices", baseURL), { signal: controller.signal });
    contentType = res.headers.get("content-type");
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const data = block
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trim())
          .join("\n");
        if (data) events.push(JSON.parse(data));
      }
      if (predicate(events)) break;
    }
  } catch (err) {
    if (!(err instanceof Error && err.name === "AbortError")) throw err;
  } finally {
    clearTimeout(timer);
    controller.abort();
  }
  return { events, contentType };
}
