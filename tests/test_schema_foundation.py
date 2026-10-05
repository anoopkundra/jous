"""Offline PostgreSQL schema and migration checks; never uses SQLite."""

import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from jous_api.models import Base


ROOT = Path(__file__).resolve().parents[1]
INI = ROOT / "services/api/alembic.ini"
REVISION = "0001_identity_project"
EXPECTED = {
    "users": {"id", "auth_issuer", "auth_subject", "status", "created_at", "updated_at"},
    "organizations": {"id", "name", "status", "created_at", "updated_at"},
    "organization_memberships": {"id", "organization_id", "user_id", "role", "status", "created_at", "updated_at"},
    "projects": {"id", "organization_id", "name", "description", "status", "created_at", "updated_at"},
}


class SchemaTests(unittest.TestCase):
    def test_exact_tables_columns_and_neutral_boundaries(self):
        self.assertEqual(set(Base.metadata.tables), set(EXPECTED))
        for table in Base.metadata.tables.values():
            self.assertEqual(set(table.c.keys()), EXPECTED[table.name])
            for column in table.c:
                for prohibited in ("balance", "spend", "reward", "supplier", "model", "memory",
                                   "mem0", "letta", "graphiti", "langmem", "vector", "provider", "token", "password"):
                    self.assertNotIn(prohibited, column.name)

    def test_uuid_pks_timestamps_and_nullability(self):
        for table in Base.metadata.tables.values():
            self.assertEqual(table.primary_key.name, "pk_" + table.name)
            self.assertEqual(list(table.primary_key.columns.keys()), ["id"])
            self.assertIsInstance(table.c.id.type, postgresql.UUID)
            self.assertIsNotNone(table.c.id.default)
            for name in ("created_at", "updated_at"):
                self.assertTrue(table.c[name].type.timezone)
                self.assertFalse(table.c[name].nullable)
                self.assertIsNotNone(table.c[name].server_default)
            self.assertIsNotNone(table.c.updated_at.onupdate)
            for column in table.c:
                self.assertEqual(column.nullable, column.name in {"auth_issuer", "auth_subject", "description"})

    def test_ownership_foreign_keys_and_restrict_deletion(self):
        expected = {
            "organization_memberships": {("organization_id", "organizations.id"), ("user_id", "users.id")},
            "projects": {("organization_id", "organizations.id")},
            "users": set(), "organizations": set(),
        }
        for table in Base.metadata.tables.values():
            self.assertEqual({(fk.parent.name, fk.target_fullname) for fk in table.foreign_keys}, expected[table.name])
            for constraint in table.constraints:
                if isinstance(constraint, ForeignKeyConstraint):
                    self.assertEqual(constraint.ondelete, "RESTRICT")
                    self.assertIsNotNone(constraint.name)

    def test_membership_uniqueness_and_indexes(self):
        membership = Base.metadata.tables["organization_memberships"]
        uniques = [c for c in membership.constraints if isinstance(c, UniqueConstraint)]
        self.assertEqual([(c.name, list(c.columns.keys())) for c in uniques],
                         [("uq_organization_memberships_organization_user", ["organization_id", "user_id"])])
        self.assertEqual({i.name for i in membership.indexes}, {"ix_organization_memberships_user_id"})
        self.assertEqual({i.name for i in Base.metadata.tables["projects"].indexes}, {"ix_projects_organization_id"})

    def test_authentication_linkage_is_nullable_paired_and_unique(self):
        users = Base.metadata.tables["users"]
        self.assertTrue(users.c.auth_issuer.nullable and users.c.auth_subject.nullable)
        self.assertTrue(any(isinstance(c, UniqueConstraint) and list(c.columns.keys()) == ["auth_issuer", "auth_subject"]
                            for c in users.constraints))
        self.assertTrue(any(isinstance(c, CheckConstraint) and c.name == "ck_users_auth_identity_pair"
                            for c in users.constraints))

    def test_postgresql_ddl_and_named_constraints(self):
        for table in Base.metadata.tables.values():
            ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
            self.assertIn("TIMESTAMP WITH TIME ZONE", ddl)
            self.assertIn("UUID", ddl)
            self.assertTrue(all(constraint.name for constraint in table.constraints))


class MigrationTests(unittest.TestCase):
    def test_single_initial_revision_has_upgrade_and_downgrade(self):
        script = ScriptDirectory.from_config(Config(str(INI)))
        self.assertEqual(script.get_heads(), ["0002_runtime_rls"])
        revisions = list(script.walk_revisions())
        self.assertEqual(len(revisions), 2)
        self.assertIsNone(revisions[-1].down_revision)
        self.assertTrue(callable(revisions[0].module.upgrade))
        self.assertTrue(callable(revisions[0].module.downgrade))

    def test_offline_migration_sql_is_deterministic_and_bounded(self):
        def render(upgrade):
            output = io.StringIO()
            config = Config(str(INI), output_buffer=output)
            if upgrade:
                command.upgrade(config, REVISION, sql=True)
            else:
                command.downgrade(config, REVISION + ":base", sql=True)
            return output.getvalue()
        with patch("asyncpg.connect", new_callable=AsyncMock) as connect:
            upgrade, downgrade = render(True), render(False)
            self.assertEqual(upgrade, render(True))
            connect.assert_not_called()
        for table in EXPECTED:
            self.assertIn("CREATE TABLE public." + table, upgrade)
            self.assertIn("DROP TABLE public." + table, downgrade)
        self.assertEqual(upgrade.count("CREATE TABLE "), 5)  # Four records plus Alembic history.
        self.assertEqual(downgrade.count("DROP TABLE "), 4)  # Empty Alembic history table remains.
        self.assertEqual(upgrade.count("ON DELETE RESTRICT"), 3)
        self.assertNotIn("CASCADE", downgrade)
        self.assertNotIn("auth.users", upgrade + downgrade)
        self.assertNotIn("CREATE POLICY", upgrade)

    def test_configuration_and_offline_sql_never_expose_url(self):
        config = Config(str(INI))
        self.assertIsNone(config.get_main_option("sqlalchemy.url"))
        output = io.StringIO()
        with patch.dict("os.environ", {"JOUS_DATABASE_URL": "postgresql://private:secret@private-host/jous"}, clear=True):
            command.upgrade(Config(str(INI), output_buffer=output), "head", sql=True)
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("private-host", output.getvalue())

    def test_importing_model_and_migration_infrastructure_never_connects(self):
        subprocess.run([sys.executable, "-c", "from unittest.mock import AsyncMock, patch; "
                        "guard = patch('asyncpg.connect', new_callable=AsyncMock); "
                        "connect = guard.start(); import jous_api.persistence; import jous_api.models; "
                        "connect.assert_not_called(); guard.stop()"], check=True)
        with patch("asyncpg.connect", new_callable=AsyncMock) as connect:
            path = ROOT / "services/api/migrations/env.py"
            spec = importlib.util.spec_from_file_location("offline_migration_environment", path)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            connect.assert_not_called()
