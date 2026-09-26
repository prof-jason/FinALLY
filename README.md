# FinAlly — AI Trading Workstation

FinAlly (Finance Ally) is an AI-powered trading workstation. It streams live market data, lets you trade a simulated $10,000 portfolio, and includes an LLM chat assistant that can analyze your positions and place trades for you. Think of a Bloomberg-style terminal with an AI copilot.

This is the capstone project for an agentic AI coding course: the whole application is built by coding agents that coordinate through the shared documents in [`planning/`](planning/).

## Project Status

| Component | Status |
|---|---|
| Specification ([`planning/PLAN.md`](planning/PLAN.md)) | Complete |
| Market data (simulator + Massive client, SSE stream) | Designed and reviewed. See [`planning/MARKET_DATA_SUMMARY.md`](planning/MARKET_DATA_SUMMARY.md) |
| Backend API, database, LLM chat | Not started |
| Frontend | Not started |
| Docker image, start/stop scripts | Not started |
| E2E tests | Not started |

Commands below that depend on unbuilt pieces (Docker, `scripts/`) describe the planned workflow.

## Features

- **Live price streaming** over Server-Sent Events. Prices flash green or red on each tick.
- **Watchlist** of 10 default tickers with sparklines drawn from the live stream. Add or remove tickers by hand or through the AI.
- **Simulated trading**: market orders only, instant fills, fractional shares, long-only (no shorting or margin), no fees.
- **Portfolio views**: a treemap heatmap sized by weight and colored by P&L, a portfolio value chart, a positions table, and trade history.
- **AI chat assistant** that analyzes the portfolio and auto-executes the trades and watchlist changes it proposes. Each action's result appears inline.
- **One-click reset** back to $10,000 cash and the default watchlist.
- **No login.** Open the page and start trading.

## Architecture

Everything runs in one Docker container on port 8000.

```
┌───────────────────────────────────────────────┐
│  Docker container (port 8000)                 │
│                                               │
│  FastAPI (Python, uv)                         │
│  ├── /api/*          REST endpoints           │
│  ├── /api/stream/*   SSE price stream         │
│  └── /*              Next.js static export    │
│                                               │
│  SQLite (db/finally.db, volume-mounted)       │
│  Background tasks: market data, snapshots     │
└───────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript (static export), Tailwind CSS, Lightweight Charts |
| Backend | FastAPI, managed with `uv` |
| Database | SQLite, created and seeded automatically on first run |
| Real-time data | Server-Sent Events (`EventSource`) |
| AI | LiteLLM → OpenRouter → `nvidia/nemotron-3-super-120b-a12b:free`, with structured outputs |
| Market data | Built-in GBM simulator by default, or the Massive (Polygon.io) REST API if a key is set |

The project uses only free (`:free`) OpenRouter models, so running it costs nothing.

## Quick Start (planned)

```bash
# 1. Configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# 2. Start (builds the image on first run)
./scripts/start_mac.sh          # macOS / Linux
./scripts/start_windows.ps1     # Windows PowerShell

# 3. Open http://localhost:8000
```

Or run Docker directly:

```bash
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

Stop the app with `./scripts/stop_mac.sh` (or `stop_windows.ps1`). Your data is kept in the `finally-data` volume.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for the AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data. Leave empty to use the simulator. |
| `LLM_MOCK` | No | Set to `true` for deterministic mock LLM responses (tests, or development without a key) |

In Docker, variables are passed with `--env-file .env`. For local development, the backend loads `.env` from the project root.

## API Overview

| Method | Path | Description |
|---|---|---|
| GET | `/api/stream/prices` | SSE stream of live prices |
| GET | `/api/portfolio` | Cash, positions, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, side, quantity}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots (last 10 days) |
| GET | `/api/portfolio/trades` | Trade history, newest first (`?limit=`, default 100) |
| POST | `/api/portfolio/reset` | Reset to $10,000 cash and the default watchlist |
| GET | `/api/watchlist` | Watchlist with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |
| POST | `/api/chat` | Send a message to the AI and get its reply plus executed actions |
| GET | `/api/health` | Health check |

Errors return `{"error": "<message>"}` with status `400` (validation) or `404` (unknown resource). Full contracts are in [`planning/PLAN.md`](planning/PLAN.md) §8.

## Testing

- **Backend**: pytest, inside `backend/` (`uv run pytest`)
- **Frontend**: component tests, inside `frontend/`
- **End-to-end**: Playwright tests in `test/`, run with `docker-compose.test.yml` and `LLM_MOCK=true`

## Project Structure

```
finally/
├── frontend/     # Next.js TypeScript project (static export)
├── backend/      # FastAPI uv project (API, SSE, market data, LLM, database)
│   └── db/       # Schema and seed logic
├── planning/     # Specs and shared contracts for the agents
├── scripts/      # Start/stop scripts for macOS/Linux and Windows
├── test/         # Playwright E2E tests
├── db/           # Runtime volume mount; finally.db lives here (gitignored)
├── Dockerfile    # Multi-stage build: Node → Python
└── .env.example  # Template for environment variables
```

## Agent Tooling

The repo includes configuration for the coding agents that build it:

- `.claude/agents/`: review subagents (`change-reviewer`, `reviewer`) that write feedback to `planning/REVIEW.md`
- `.claude/commands/doc-review.md`: `/doc-review` command for reviewing planning documents
- `.claude/settings.json`: enabled Claude Code plugins
- `.github/workflows/`: Claude GitHub Actions for `@claude` mentions and automated PR review

## License

See [LICENSE](LICENSE).
