"""Watchlist routes."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app import services

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str


@router.get("")
def get_watchlist() -> dict:
    return {"watchlist": services.get_watchlist()}


@router.post("", status_code=201)
async def add_ticker(body: AddTickerRequest) -> dict:
    return await services.add_watchlist_ticker(body.ticker)


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(ticker: str) -> Response:
    await services.remove_watchlist_ticker(ticker)
    return Response(status_code=204)
