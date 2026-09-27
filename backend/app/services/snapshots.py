"""Background task recording portfolio snapshots (PLAN §7)."""

from __future__ import annotations

import asyncio
import logging

from .portfolio import record_snapshot

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30.0


async def snapshot_loop(interval: float = SNAPSHOT_INTERVAL) -> None:
    """Record a snapshot and prune old ones every `interval` seconds, forever.

    Runs whether or not any client is connected; a failed tick is logged and
    the loop carries on.
    """
    while True:
        try:
            record_snapshot()
        except Exception:
            logger.exception("Portfolio snapshot failed")
        await asyncio.sleep(interval)


def start_snapshot_task(interval: float = SNAPSHOT_INTERVAL) -> asyncio.Task:
    return asyncio.create_task(snapshot_loop(interval), name="portfolio-snapshots")


async def stop_snapshot_task(task: asyncio.Task | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
