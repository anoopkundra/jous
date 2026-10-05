"""Asyncpg migrations through Jous settings; offline SQL requires no credentials."""

import asyncio

from alembic import context

from jous_api.config import ConfigurationError, load_migration_settings
from jous_api.database import Database
from jous_api.models import Base


def include_name(name, type_, parent_names):
    """Never autogenerate against Supabase-managed or unrelated objects."""
    if type_ == "schema":
        return name in (None, "public")
    if type_ == "table":
        return name in {table.name for table in Base.metadata.tables.values()}
    return True


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata,
                      include_schemas=True, include_name=include_name,
                      version_table_schema="public", compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    database = Database(load_migration_settings())
    if database.engine is None:
        raise ConfigurationError("Migrations require JOUS_MIGRATION_DATABASE_URL")
    try:
        async with database.engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await database.dispose()


def main():
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", literal_binds=True,
                          target_metadata=Base.metadata, version_table_schema="public")
        with context.begin_transaction():
            context.run_migrations()
    elif context.config.attributes.get("connection") is not None:
        run_migrations(context.config.attributes["connection"])
    else:
        # Migration failures must not print driver exceptions containing secrets.
        try:
            asyncio.run(run_online())
        except ConfigurationError:
            raise
        except Exception:
            raise RuntimeError("Jous migration failed; inspect target and configuration securely") from None


if __name__ in {"env_py", "__main__"}:
    main()
