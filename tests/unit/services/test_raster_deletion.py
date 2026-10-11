import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from services.data_service.crud import raster_crud
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.models import RasterMetadata


class AsyncSessionAdapter:
    """Exercise real ORM transactions with SQLite; record PostgreSQL table locks."""

    def __init__(self, session):
        self.session = session
        self.events = []
        self.fail_commit = False
        self.fail_reference_check = False
        self.after_commit = None

    async def execute(self, statement):
        if isinstance(statement, TextClause):
            assert str(statement) == "LOCK TABLE raster_metadata IN SHARE ROW EXCLUSIVE MODE"
            self.events.append("lock")
            return None
        if self.fail_reference_check and "commit" in self.events:
            raise RuntimeError("reference check unavailable")
        return self.session.execute(statement)

    async def delete(self, item):
        self.session.delete(item)

    def add(self, item):
        self.session.add(item)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.session.commit()
        self.events.append("commit")
        if self.after_commit:
            self.after_commit()

    async def rollback(self):
        self.session.rollback()
        self.events.append("rollback")


@pytest.fixture
def storage_db(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    raw = storage / "raw" / "source.tif"
    cog = storage / "cog" / "source.tif"
    for path in (raw, cog):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"raster")
    monkeypatch.setattr(raster_crud, "STORAGE_DIR", storage)
    engine = create_engine("sqlite://")
    RasterMetadata.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield AsyncSessionAdapter(session), raw, cog
    engine.dispose()


def add_raster(db, raw, cog="/data/source.tif", index_id=1):
    record = RasterMetadata(file_name="source.tif", index_id=index_id, file_path=str(raw), cog_path=cog)
    db.session.add(record)
    db.session.commit()
    return record.id


def test_shared_files_survive_until_last_reference(storage_db, monkeypatch):
    db, raw, cog = storage_db
    first_id = add_raster(db, raw)
    # Different path representations resolve to the same COG asset.
    second_id = add_raster(db, raw, str(cog), index_id=2)
    original_delete = RasterCRUD._delete_file

    def checked_delete(path):
        assert db.events.index("commit") < len(db.events) - 1
        assert db.events[-1] == "lock"
        original_delete(path)

    monkeypatch.setattr(RasterCRUD, "_delete_file", checked_delete)
    assert asyncio.run(RasterCRUD.delete_raster(db, first_id))
    assert raw.exists() and cog.exists()
    assert asyncio.run(RasterCRUD.delete_raster(db, second_id))
    assert not raw.exists() and not cog.exists()
    assert db.session.scalars(select(RasterMetadata)).all() == []


@pytest.mark.parametrize("clear_all", [False, True])
def test_failed_commit_never_unlinks_files(storage_db, clear_all):
    db, raw, cog = storage_db
    record_id = add_raster(db, raw)
    db.fail_commit = True
    operation = RasterCRUD.clear_all_rasters(db) if clear_all else RasterCRUD.delete_raster(db, record_id)
    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(operation)
    asyncio.run(db.rollback())
    assert raw.exists() and cog.exists()
    assert db.session.get(RasterMetadata, record_id) is not None


def test_clear_deduplicates_shared_files_and_skips_external_paths(storage_db, monkeypatch, tmp_path):
    db, raw, cog = storage_db
    add_raster(db, raw)
    add_raster(db, raw, str(cog), index_id=2)
    outside = tmp_path / "external.tif"
    outside.write_bytes(b"external")
    add_raster(db, outside, str(outside), index_id=3)
    deleted = []
    original_delete = RasterCRUD._delete_file

    def record_delete(path):
        deleted.append(Path(path))
        original_delete(path)

    monkeypatch.setattr(RasterCRUD, "_delete_file", record_delete)
    assert asyncio.run(RasterCRUD.clear_all_rasters(db))
    assert set(deleted) == {raw, cog} and len(deleted) == 2
    assert outside.exists()
    assert db.session.scalars(select(RasterMetadata)).all() == []


def test_cross_column_reference_preserves_asset(storage_db):
    db, raw, cog = storage_db
    first_id = add_raster(db, raw)
    add_raster(db, cog, None, index_id=2)
    assert asyncio.run(RasterCRUD.delete_raster(db, first_id))
    assert not raw.exists() and cog.exists()


def test_reference_added_after_delete_commit_is_preserved(storage_db):
    db, raw, cog = storage_db
    record_id = add_raster(db, raw)
    db.after_commit = lambda: add_raster(db, raw, index_id=2)
    assert asyncio.run(RasterCRUD.delete_raster(db, record_id))
    assert raw.exists() and cog.exists()


def test_failed_reference_check_keeps_files_and_releases_lock(storage_db):
    db, raw, cog = storage_db
    record_id = add_raster(db, raw)
    db.fail_reference_check = True
    assert asyncio.run(RasterCRUD.delete_raster(db, record_id))
    assert raw.exists() and cog.exists()
    assert db.events[-1] == "rollback"
    assert db.session.get(RasterMetadata, record_id) is None


def test_public_path_traversal_cannot_escape_managed_storage(storage_db):
    assert RasterCRUD._physical_paths(None, "/data/../../external.tif") == set()


def test_missing_record_releases_write_lock(storage_db):
    db, raw, cog = storage_db
    assert not asyncio.run(RasterCRUD.delete_raster(db, 999))
    assert db.events == ["lock", "rollback"]
    assert raw.exists() and cog.exists()


def test_cancelled_request_holds_lock_until_file_thread_finishes(storage_db, monkeypatch):
    db, raw, cog = storage_db
    record_id = add_raster(db, raw)
    finish = threading.Event()
    original_delete = RasterCRUD._delete_paths

    async def scenario():
        started = asyncio.Event()
        loop = asyncio.get_running_loop()

        def delayed_delete(paths):
            loop.call_soon_threadsafe(started.set)
            assert finish.wait(timeout=5)
            original_delete(paths)

        monkeypatch.setattr(RasterCRUD, "_delete_paths", delayed_delete)
        task = asyncio.create_task(RasterCRUD.delete_raster(db, record_id))
        try:
            await asyncio.wait_for(started.wait(), timeout=3)
            task.cancel()
            await asyncio.sleep(0)
            assert "rollback" not in db.events
            assert raw.exists() and cog.exists()
        finally:
            finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert db.events[-1] == "rollback"
    assert not raw.exists() and not cog.exists()


@pytest.mark.parametrize("source_deleted", [False, True])
def test_ai_copy_rechecks_source_under_write_lock(storage_db, monkeypatch, source_deleted):
    from services.ai_gateway import modify_handler
    from services.ai_gateway.schema_validator import AILanguage, DataType, RasterModifiable

    db, raw, cog = storage_db
    record_id = add_raster(db, raw)
    context = SimpleNamespace(model_dump_json=lambda **kwargs: "{}")
    monkeypatch.setattr(modify_handler, "_extract_raster_data", AsyncMock(return_value=context))
    monkeypatch.setattr(modify_handler, "_build_system_prompt", lambda *args: "modify")
    monkeypatch.setattr(modify_handler, "get_next_index_id", lambda: 2)

    async def fake_llm(*args):
        if source_deleted:
            db.session.delete(db.session.get(RasterMetadata, record_id))
            db.session.commit()
        return RasterModifiable(name="copy")

    monkeypatch.setattr(modify_handler, "call_llm_with_retry", fake_llm)
    original_get = RasterCRUD.get_raster_by_index_id

    async def checked_get(session, index_id):
        assert session.events[-1] == "lock"
        return await original_get(session, index_id)

    monkeypatch.setattr(RasterCRUD, "get_raster_by_index_id", checked_get)
    payload = SimpleNamespace(
        data_type=DataType.RASTER, target_id=1, overwrite=False,
        user_prompt="create a copy", language=AILanguage.EN,
    )
    if source_deleted:
        with pytest.raises(ValueError, match="index_id not found"):
            asyncio.run(modify_handler.handle_modify(payload, db, None, "test-model"))
        assert db.session.scalars(select(RasterMetadata)).all() == []
    else:
        result = asyncio.run(modify_handler.handle_modify(payload, db, None, "test-model"))
        assert result["new_index_id"] == 2 and db.events == ["lock", "commit"]
        copy = db.session.scalars(select(RasterMetadata).where(RasterMetadata.index_id == 2)).one()
        assert copy.file_path == str(raw) and copy.cog_path == "/data/source.tif"
    assert raw.exists() and cog.exists()
