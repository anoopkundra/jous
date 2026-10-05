"""Explicit destructive cycle for an EMPTY dedicated managed test database only.

Not discovered by unittest. Requires exported Jous settings and a target fingerprint.
Never prints driver errors, URLs or credentials. Stops before downgrade on ambiguity.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from jous_api.config import load_migration_settings
from jous_api.database import Database
from jous_api.models import Base

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0001_identity_project"
TABLES = {table.name for table in Base.metadata.tables.values()}
PUBLIC_RELATIONS = TABLES | {"alembic_version", "alembic_version_pkc"} | {
    constraint.name for table in Base.metadata.tables.values() for constraint in table.constraints
    if isinstance(constraint, (PrimaryKeyConstraint, UniqueConstraint))
} | {index.name for table in Base.metadata.tables.values() for index in table.indexes}


class SafetyStop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise SafetyStop(message)


async def snapshot(engine):
    async with engine.connect() as connection:
        public = (await connection.execute(text(
            "SELECT relname, relkind, relrowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1"
        ))).all()
        managed = (await connection.execute(text(
            "SELECT n.nspname, c.relname, c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname NOT IN ('public','information_schema') ORDER BY 1,2"
        ))).all()
        extensions = (await connection.execute(text("SELECT extname, oid FROM pg_extension ORDER BY 1"))).all()
        return public, managed, extensions


async def migrate(engine, action):
    async with engine.begin() as connection:
        def run(sync_connection):
            config = Config(str(ROOT / "services/api/alembic.ini"))
            config.attributes["connection"] = sync_connection
            if action == "upgrade":
                command.upgrade(config, REVISION)
            else:
                command.downgrade(config, "base")
        await connection.run_sync(run)
    print("ALEMBIC " + action.upper() + ": PASS")


async def validate_schema(engine):
    async with engine.connect() as connection:
        def verify(sync_connection):
            inspector = inspect(sync_connection)
            require(set(inspector.get_table_names(schema="public")) == TABLES | {"alembic_version"},
                    "Unexpected application tables; stop before downgrade")
            for table in Base.metadata.tables.values():
                require(inspector.get_pk_constraint(table.name, schema="public")["name"] == table.primary_key.name,
                        "Primary key mismatch")
                require({column["name"] for column in inspector.get_columns(table.name, schema="public")} == set(table.c.keys()),
                        "Column mismatch")
                require({item["name"] for item in inspector.get_check_constraints(table.name, schema="public")} ==
                        {constraint.name for constraint in table.constraints if constraint.__class__.__name__ == "CheckConstraint"},
                        "Check constraint mismatch")
                for fk in inspector.get_foreign_keys(table.name, schema="public"):
                    require(fk["options"].get("ondelete") == "RESTRICT", "Unsafe deletion semantics")
            def include_name(name, type_, parent_names):
                return name in (None, "public") if type_ == "schema" else name in TABLES if type_ == "table" else True
            context = MigrationContext.configure(sync_connection, opts={
                "include_schemas": True, "include_name": include_name,
                "compare_type": True, "compare_server_default": True,
                "version_table_schema": "public"})
            require(not compare_metadata(context, Base.metadata), "Live schema differs from ORM metadata")
        await connection.run_sync(verify)
        revision = (await connection.execute(text("SELECT version_num FROM public.alembic_version"))).scalars().all()
        require(revision == [REVISION], "Unexpected revision state")
        rls = (await connection.execute(text(
            "SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' ORDER BY 1"))).all()
        print("SCHEMA / REVISION / METADATA: PASS")
        print("PLATFORM RLS:", json.dumps({row[0]: row[1] for row in rls}))


async def validate_constraints(engine):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            user, organization, project = uuid4(), uuid4(), uuid4()
            await connection.execute(text("INSERT INTO public.users (id) VALUES (:id)"), {"id": user})
            await connection.execute(text("INSERT INTO public.organizations (id, name) VALUES (:id, 'validation')"), {"id": organization})
            await connection.execute(text("INSERT INTO public.projects (id, organization_id, name) VALUES (:id, :org, 'validation')"),
                                     {"id": project, "org": organization})
            membership_sql = text("INSERT INTO public.organization_memberships (id, organization_id, user_id) VALUES (:id, :org, :user)")
            await connection.execute(membership_sql, {"id": uuid4(), "org": organization, "user": user})
            async def reject(statement, params, sqlstate):
                savepoint = await connection.begin_nested()
                try:
                    await connection.execute(statement, params)
                except IntegrityError as error:
                    require(getattr(error.orig, "sqlstate", None) == sqlstate, "Unexpected constraint failure")
                else:
                    raise SafetyStop("Expected constraint was not enforced")
                finally:
                    await savepoint.rollback()
            await reject(membership_sql, {"id": uuid4(), "org": organization, "user": user}, "23505")
            await reject(text("INSERT INTO public.projects (id, organization_id, name) VALUES (:id, :org, 'invalid')"),
                         {"id": uuid4(), "org": uuid4()}, "23503")
            await reject(text("DELETE FROM public.organizations WHERE id=:id"), {"id": organization}, "23503")
            await reject(text("DELETE FROM public.users WHERE id=:id"), {"id": user}, "23503")
            await reject(text("INSERT INTO public.users (id, auth_issuer) VALUES (:id, 'issuer')"), {"id": uuid4()}, "23514")
            await reject(text("INSERT INTO public.organizations (id, name) VALUES (:id, ' ')"), {"id": uuid4()}, "23514")
            await reject(text("UPDATE public.organization_memberships SET role='' WHERE user_id=:id"), {"id": user}, "23514")
        finally:
            await transaction.rollback()
    print("CONSTRAINT ENFORCEMENT / TEST DATA ROLLBACK: PASS")


async def main(expected_fingerprint):
    raise SafetyStop("Legacy Step 4 cycle retired; use reviewed Step 7 validation")
    settings = load_migration_settings()
    require(settings.environment != "production", "Production configuration refused")
    require(settings.database_url is not None, "JOUS_DATABASE_URL is required")
    url = make_url(settings.database_url.get_secret_value())
    fingerprint = hashlib.sha256((url.host + ':' + str(url.port) + '/' + url.database + '/' + (url.username or '')).encode()).hexdigest()[:16]
    require(fingerprint == expected_fingerprint, "Target fingerprint mismatch")
    database = Database(settings)
    try:
        before, managed, extensions = await snapshot(database.engine)
        require(not before, "Public schema is not empty; destructive cycle refused")
        print("EMPTY TARGET CONFIRMED:", fingerprint)
        await migrate(database.engine, "upgrade")
        await validate_schema(database.engine)
        await validate_constraints(database.engine)
        public, current_managed, current_extensions = await snapshot(database.engine)
        require(current_managed == managed and current_extensions == extensions, "Managed objects changed; stop before downgrade")
        require({row[0] for row in public} == PUBLIC_RELATIONS, "Unexpected relations; stop before downgrade")
        async with database.engine.connect() as connection:
            for table in TABLES:
                require(await connection.scalar(text('SELECT count(*) FROM public.' + table)) == 0,
                        "Application data present; stop before downgrade")
        await migrate(database.engine, "downgrade")
        public, current_managed, current_extensions = await snapshot(database.engine)
        require({row[0] for row in public} == {"alembic_version", "alembic_version_pkc"}, "Step 4 objects were not fully removed")
        require(current_managed == managed and current_extensions == extensions, "Managed objects changed")
        async with database.engine.connect() as connection:
            require(await connection.scalar(text("SELECT count(*) FROM public.alembic_version")) == 0, "Downgrade revision is not base")
        print("DOWNGRADE TO BASE / OBJECT REMOVAL / MANAGED OBJECTS: PASS")
        await migrate(database.engine, "upgrade")
        await validate_schema(database.engine)
        public, current_managed, current_extensions = await snapshot(database.engine)
        require(current_managed == managed and current_extensions == extensions, "Managed objects changed")
        print("FINAL DATABASE HEAD:", REVISION)
    finally:
        await database.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-fingerprint", required=True)
    arguments = parser.parse_args()
    try:
        asyncio.run(main(arguments.target_fingerprint))
    except SafetyStop as error:
        print("SAFETY STOP:", str(error))
        raise SystemExit(1)
    except Exception as error:
        print("VALIDATION FAILED:", type(error).__name__, "(details suppressed; inspect securely)")
        raise SystemExit(1)
