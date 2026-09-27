import pytest

from app import db
from app.market import PriceCache, SimulatorDataSource
from app.services import state


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "finally.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    db.init_db()
    return path


@pytest.fixture
async def market(db_path):
    """A started simulator (stepping only once) wired into app.services.state."""
    cache = PriceCache()
    source = SimulatorDataSource(cache, update_interval=3600, seed=7)
    state.configure(cache, source)
    await source.start(list(db.DEFAULT_WATCHLIST))
    yield cache, source
    await source.stop()
    state.clear()


@pytest.fixture
def cache(market):
    return market[0]


@pytest.fixture
def source(market):
    return market[1]
