"""Alembic environment configuration for Loka backend."""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import app settings and models
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.core.database import Base

# Import all models so their tables are registered in Base.metadata
from app.models import citizen, district, issue, participation, comment, comment_like, comment_report, evidence, notification, moderation  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.databaseUrl.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def runMigrationsOffline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def doRunMigrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def runMigrationsOnline() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(doRunMigrations)
    await connectable.dispose()


if context.is_offline_mode():
    runMigrationsOffline()
else:
    asyncio.run(runMigrationsOnline())
