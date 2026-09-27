"""Portfolio routes: valuation, trades, history, reset."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app import services

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    side: str
    # Validated in the service so every bad value gets the same error message
    quantity: Any


@router.get("")
def get_portfolio() -> dict:
    return services.get_portfolio()


@router.post("/trade")
async def trade(body: TradeRequest) -> dict:
    return await services.execute_trade(body.ticker, body.side, body.quantity)


@router.get("/history")
def history() -> dict:
    return {"snapshots": services.get_history()}


@router.get("/trades")
def trades(limit: int = Query(100, ge=1, le=1000)) -> dict:
    return {"trades": services.get_trades(limit)}


@router.post("/reset")
async def reset() -> dict:
    return await services.reset_portfolio()
