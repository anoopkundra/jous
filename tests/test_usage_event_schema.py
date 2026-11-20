"""V1.4B migration/source contract tests; no database is contacted."""
import ast
import importlib.util
from pathlib import Path
import re
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from jous_api.models import Base
from jous_api.usage_event_models import usage_events
from jous_api.usage_event_validation import (REVISION, DEFAULT_ACL_SQL,
    ROLE_RELATION_AUTHORITY_SQL, _expected_constraints, _expected_columns,
    _types_equivalent)

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "services/api/migrations/versions/0007_usage_events.py"
SPEC = importlib.util.spec_from_file_location("usage_events_migration", PATH)
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


class UsageEventMigrationTests(unittest.TestCase):
    def test_linear_revision_and_single_additive_relation(self):
        self.assertEqual(MIGRATION.revision, "0007_usage_events")
        self.assertEqual(MIGRATION.down_revision, "0006_snapshot_binding")
        self.assertEqual(REVISION, "0008_usage_event_acl_hardening")
        sql = "\n".join(MIGRATION.UPGRADE_SQL)
        self.assertEqual(len(re.findall(r"CREATE TABLE public\.", sql)), 1)
        self.assertIn("CREATE TABLE public.usage_events", sql)
        self.assertNotIn("CREATE TABLE public.economic_receipts", sql)
        self.assertNotIn("CREATE TABLE public.ledger_", sql)
        self.assertNotIn("model_catalog", sql)
        self.assertNotIn("route_catalog", sql)

    def test_append_only_security_and_source_binding_are_explicit(self):
        sql = "\n".join(MIGRATION.UPGRADE_SQL)
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)
        self.assertIn("FORCE ROW LEVEL SECURITY", sql)
        self.assertIn("fk_usage_events_task_binding", sql)
        self.assertIn("fk_usage_events_execution", sql)
        self.assertIn("fk_usage_events_route_decision", sql)
        self.assertIn("fk_usage_events_supersession_binding", sql)
        self.assertIn("uq_usage_events_single_successor", sql)
        self.assertIn("REVOKE ALL PRIVILEGES ON TABLE public.usage_events FROM PUBLIC,jous_runtime,jous_security_reader", sql)
        self.assertRegex(sql, r"GRANT SELECT \([^)]*\) ON public\.usage_events TO jous_runtime")
        self.assertRegex(sql, r"GRANT INSERT \([^)]*\) ON public\.usage_events TO jous_runtime")
        self.assertNotRegex(sql, r"(?im)^\s*GRANT\s+(ALL|UPDATE|DELETE|TRUNCATE)\b")
        self.assertNotRegex(sql, r"(?im)^\s*(UPDATE|DELETE|TRUNCATE)\s+public\.")
        self.assertIn("CREATE POLICY jous_usage_events_insert", sql)
        self.assertIn("CREATE POLICY jous_usage_events_select", sql)
        self.assertIn("public.executions e WHERE e.id=usage_events.execution_id", sql)
        self.assertIn("source_revision='execution-row-v1'", sql)
        policy = next(statement for statement in MIGRATION.UPGRADE_SQL if statement.startswith(
            "CREATE POLICY jous_usage_events_insert"))
        self.assertIn("NOT EXISTS (SELECT 1 FROM public.route_decisions d WHERE d.task_id=usage_events.task_id)", policy)
        for binding in ("d.organization_id=usage_events.organization_id",
                        "d.project_id=usage_events.project_id",
                        "d.actor_user_id=usage_events.actor_user_id",
                        "d.dispatch_claim_id=usage_events.dispatch_claim_id",
                        "d.logical_model_id=usage_events.logical_model_id",
                        "d.logical_model_version=usage_events.logical_model_version",
                        "d.selected_route_id=usage_events.route_id",
                        "d.selected_route_version=usage_events.route_version"):
            self.assertIn(binding, policy)
        self.assertIn("jsonb_strip_nulls(pg_catalog.jsonb_build_object", policy)
        self.assertIn("usage_events.usage_status=pg_catalog.upper(e.usage_status)", policy)

    def test_migration_is_forward_only_to_protect_append_only_evidence(self):
        self.assertIn("RuntimeError", MIGRATION.downgrade.__code__.co_names)

    def test_metadata_contract_has_exact_columns_constraints_and_no_mutable_defaults(self):
        self.assertEqual(Base.metadata.tables["public.usage_events"], usage_events)
        expected = {
            "usage_event_id", "organization_id", "project_id", "actor_user_id", "task_id",
            "dispatch_claim_id", "execution_id", "route_decision_id", "logical_model_id",
            "logical_model_version", "route_id", "route_version", "supplier_id",
            "underlying_provider", "reported_provider_id", "input_tokens", "output_tokens",
            "total_tokens", "cached_input_tokens", "reasoning_tokens", "usage_status",
            "source_type", "source_reference", "source_revision", "observed_at",
            "normalizer_version", "canonical_payload", "evidence_sha256",
            "supersedes_usage_event_id", "recorded_at",
        }
        self.assertEqual(set(usage_events.c.keys()), expected)
        self.assertEqual({c.name for c in usage_events.constraints}, set(_expected_constraints()))
        self.assertEqual(set(_expected_columns()), expected)
        self.assertEqual({c.name for c in usage_events.constraints if isinstance(c, UniqueConstraint)}, {
            "uq_usage_events_source_identity", "uq_usage_events_single_successor",
            "uq_usage_events_binding"})
        self.assertEqual(usage_events.c.recorded_at.server_default.arg.text, "statement_timestamp()")
        for column in usage_events.columns:
            self.assertIsNone(column.default)
            self.assertIsNone(column.onupdate)
        task_fk = next(c for c in usage_events.constraints if isinstance(c, ForeignKeyConstraint)
                       and c.name == "fk_usage_events_task_binding")
        self.assertEqual(tuple(task_fk.columns.keys()),
                         ("task_id", "organization_id", "project_id", "actor_user_id", "dispatch_claim_id"))

    def test_one_linear_migration_head(self):
        scripts = ScriptDirectory.from_config(Config(str(ROOT / "services/api/alembic.ini")))
        self.assertEqual(scripts.get_heads(), ["0008_usage_event_acl_hardening"])
        self.assertEqual(scripts.get_revision("0007_usage_events").down_revision, "0006_snapshot_binding")
        self.assertEqual(scripts.get_revision("0008_usage_event_acl_hardening").down_revision,
                         "0007_usage_events")

    def test_0008_revokes_relation_and_future_default_authority(self):
        path = ROOT / "services/api/migrations/versions/0008_usage_event_acl_hardening.py"
        spec = importlib.util.spec_from_file_location("usage_event_acl_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        sql = "\n".join(migration.UPGRADE_SQL)
        self.assertEqual((migration.revision, migration.down_revision),
                         ("0008_usage_event_acl_hardening", "0007_usage_events"))
        self.assertIn("REVOKE TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLE public.usage_events", sql)
        self.assertIn("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE", sql)
        self.assertNotRegex(sql, r"(?im)^\s*(INSERT|UPDATE|DELETE|TRUNCATE)\s+public\.")
        self.assertNotRegex(sql, r"(?im)^\s*(CREATE ROLE|ALTER OWNER|SECURITY DEFINER)")
        self.assertIn("Unsafe global postgres table defaults require separate review", sql)

    def test_usage_validator_checks_relation_and_future_default_authority(self):
        self.assertIn("pg_default_acl", DEFAULT_ACL_SQL)
        self.assertIn("defaclnamespace IN", DEFAULT_ACL_SQL)
        self.assertIn("service_role", DEFAULT_ACL_SQL)
        self.assertIn("pg_catalog.has_table_privilege", ROLE_RELATION_AUTHORITY_SQL)
        for privilege in ("TRUNCATE", "TRIGGER", "REFERENCES", "MAINTAIN"):
            self.assertIn(privilege, ROLE_RELATION_AUTHORITY_SQL)

    def test_0007_decision_binding_constraint_identity_matches_metadata(self):
        sql = "\n".join(MIGRATION.UPGRADE_SQL)
        self.assertIn("CONSTRAINT ck_usage_events_decision_binding CHECK", sql)
        checks = {c.name for c in usage_events.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("ck_usage_events_decision_binding", checks)
        self.assertNotIn("ck_usage_events_route_decision_binding", checks)

    def test_pg_type_aliases_are_semantic_but_modifiers_remain_exact(self):
        equivalent = [
            ("UUID", "uuid"), ("VARCHAR(255)", "character varying(255)"),
            ("BIGINT", "bigint"), ("INTEGER", "int4"),
            ("TIMESTAMP WITH TIME ZONE", "timestamptz"), ("TEXT", "text"),
            ("BYTEA", "bytea"), ("NUMERIC(20, 6)", "numeric(20,6)"),
            ("INTEGER[]", "int4[][]"),
        ]
        for expected, actual in equivalent:
            with self.subTest(expected=expected, actual=actual):
                self.assertTrue(_types_equivalent(expected, actual))

    def test_pg_type_comparison_rejects_semantic_differences(self):
        different = [
            ("UUID", "text"), ("VARCHAR(255)", "varchar(256)"),
            ("BIGINT", "integer"), ("INTEGER", "bigint"),
            ("TIMESTAMP WITH TIME ZONE", "timestamp without time zone"),
            ("TEXT", "bytea"), ("BYTEA", "text"),
            ("NUMERIC(20, 6)", "numeric(20,5)"),
            ('"TenantEnum"', '"tenantenum"'),
        ]
        for expected, actual in different:
            with self.subTest(expected=expected, actual=actual):
                self.assertFalse(_types_equivalent(expected, actual))

    def test_constraint_name_matches_applied_0007_migration(self):
        sql = "\n".join(MIGRATION.UPGRADE_SQL)
        self.assertIn("CONSTRAINT ck_usage_events_decision_binding CHECK", sql)
        checks = {c.name for c in usage_events.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("ck_usage_events_decision_binding", checks)
        self.assertNotIn("ck_usage_events_route_decision_binding", checks)
