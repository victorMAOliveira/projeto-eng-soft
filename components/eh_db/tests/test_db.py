import textwrap
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import String, create_engine, inspect
from sqlalchemy.orm import Mapped, mapped_column

from eh_db import Base, BaseRepository, Database, SqlIdempotencyStore, TimestampMixin


class Widget(TimestampMixin, Base):
    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(20), default="blue")


class WidgetRepository(BaseRepository[Widget]):
    model = Widget


@pytest.fixture
async def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.create_all(Base.metadata)
    yield database
    await database.dispose()


async def test_repository_crud(db: Database):
    async with db.session() as session:
        repo = WidgetRepository(session)
        a = await repo.add(Widget(name="a", color="red"))
        await repo.add(Widget(name="b"))
        await repo.add(Widget(name="c", color="red"))
        assert a.id is not None
        assert a.created_at is not None

    async with db.session() as session:
        repo = WidgetRepository(session)
        assert (await repo.get(a.id)).name == "a"
        assert await repo.count() == 3
        assert await repo.count(color="red") == 2
        reds = await repo.list(color="red", order_by=[Widget.name.desc()])
        assert [w.name for w in reds] == ["c", "a"]
        assert len(await repo.list(offset=1, limit=1)) == 1
        await repo.delete(reds[0])

    async with db.session() as session:
        assert await WidgetRepository(session).count() == 2


async def test_updated_at_is_available_after_update_without_lazy_io(db: Database):
    async with db.session() as session:
        widget = await WidgetRepository(session).add(Widget(name="w"))
    async with db.session() as session:
        widget = await WidgetRepository(session).get(widget.id)
        widget.color = "green"
        await session.flush()
        assert widget.updated_at is not None  # would raise MissingGreenlet without eager_defaults


async def test_session_rolls_back_on_error(db: Database):
    with pytest.raises(RuntimeError):
        async with db.session() as session:
            session.add(Widget(name="lost"))
            await session.flush()
            raise RuntimeError("boom")
    async with db.session() as session:
        assert await WidgetRepository(session).count() == 0


async def test_get_session_dependency_and_ping(db: Database):
    assert await db.ping() is True
    generator = db.get_session()
    session = await generator.__anext__()
    session.add(Widget(name="dep"))
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()
    async with db.session() as check:
        assert await WidgetRepository(check).count(name="dep") == 1


async def test_idempotency_store(db: Database):
    store = SqlIdempotencyStore(db)
    assert await store.seen("evt-1") is False
    await store.mark("evt-1", "user.registered")
    assert await store.seen("evt-1") is True
    await store.mark("evt-1", "user.registered")  # duplicate is ignored
    assert await store.seen("evt-1") is True


def test_postgres_options_are_applied():
    database = Database("postgresql+asyncpg://u:p@localhost:5432/db")
    assert database.engine.pool.size() == 5


def test_run_migrations_offline_and_online(tmp_path: Path, monkeypatch):
    script_dir = tmp_path / "alembic"
    (script_dir / "versions").mkdir(parents=True)
    (script_dir / "script.py.mako").write_text("")
    (script_dir / "env.py").write_text(
        textwrap.dedent(
            """
            from eh_db import Base, run_migrations
            run_migrations(Base.metadata)
            """
        )
    )
    (script_dir / "versions" / "0001_init.py").write_text(
        textwrap.dedent(
            """
            import sqlalchemy as sa
            from alembic import op

            revision = "0001"
            down_revision = None
            branch_labels = None
            depends_on = None

            def upgrade():
                op.create_table("things", sa.Column("id", sa.Integer, primary_key=True))

            def downgrade():
                op.drop_table("things")
            """
        )
    )
    db_file = tmp_path / "test.db"
    config = Config()
    config.set_main_option("script_location", str(script_dir))

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    command.upgrade(config, "head", sql=True)  # offline mode only prints SQL
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    assert "things" in inspect(engine).get_table_names()
    engine.dispose()

    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError):
        command.upgrade(config, "head")
