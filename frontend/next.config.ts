import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export default function config(phase: string): NextConfig {
  // `next dev` proxies /api/* to the FastAPI backend; `next build` produces a
  // static export (out/) that FastAPI serves from the same origin.
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      // gzip would buffer the proxied SSE stream until it closes.
      compress: false,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
      },
    };
  }
  return {
    output: "export",
    images: { unoptimized: true },
  };
}
