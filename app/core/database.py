from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.expression import Update, Delete, Insert, TextClause
from app.core.config import settings


class OptimizingAsyncSession(AsyncSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hasWrites = False

    async def execute(self, statement, *args, **kwargs):
        if not self.hasWrites:
            if isinstance(statement, (Update, Delete, Insert)):
                self.hasWrites = True
            elif isinstance(statement, TextClause):
                textStr = statement.text.lower()
                if any(k in textStr for k in ("insert", "update", "delete")):
                    self.hasWrites = True
            elif isinstance(statement, str):
                textStr = statement.lower()
                if any(k in textStr for k in ("insert", "update", "delete")):
                    self.hasWrites = True
        return await super().execute(statement, *args, **kwargs)

    async def flush(self, *args, **kwargs):
        self.hasWrites = True
        return await super().flush(*args, **kwargs)


engine = create_async_engine(
    settings.databaseUrl,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=30,
    max_overflow=40,
    pool_recycle=1800,
    pool_timeout=15,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=OptimizingAsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def getDb():
    async with AsyncSessionFactory() as session:
        try:
            yield session
            if session.new or session.dirty or session.deleted or getattr(session, "hasWrites", False):
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
