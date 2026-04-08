"""Create tables (development / first deploy). For migrations use Alembic in production."""

from sqlalchemy.ext.asyncio import AsyncEngine

from database.connection import engine
from database.models import Base


async def create_all(engine_: AsyncEngine | None = None) -> None:
    eng = engine_ or engine
    if eng is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

