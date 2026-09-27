import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAlly",
  description: "AI trading workstation with live prices, a simulated portfolio and an AI copilot.",
};

export const viewport: Viewport = {
  themeColor: "#0d1117",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
