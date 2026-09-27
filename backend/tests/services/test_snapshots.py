import asyncio

from app import db
from app.services import snapshot_loop, start_snapshot_task, stop_snapshot_task


def count() -> int:
    with db.get_connection() as conn:
        return len(db.list_snapshots(conn))


async def test_snapshot_task_records_periodically(cache):
    task = start_snapshot_task(interval=0.01)
    await asyncio.sleep(0.05)
    await stop_snapshot_task(task)
    assert task.done()
    assert count() >= 2


async def test_snapshot_loop_survives_errors(cache, monkeypatch):
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.snapshots.record_snapshot", boom)
    task = asyncio.create_task(snapshot_loop(0.01))
    await asyncio.sleep(0.05)
    await stop_snapshot_task(task)
    assert len(calls) >= 2


async def test_stop_is_safe_on_none_or_done():
    await stop_snapshot_task(None)
