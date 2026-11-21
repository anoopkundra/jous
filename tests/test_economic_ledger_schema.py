"""V1.4C schema contract tests; no database connection is opened."""
import ast
import importlib.util
import inspect
import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from jous_api.economic_models import (supplier_funding_authorities, economic_receipts,
    ledger_accounts, ledger_transactions, ledger_entries)
from jous_api.usage_event_validation import ECONOMIC_PROCESSOR_USAGE_COLUMNS
from test_schema_foundation import INI

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "services/api/migrations/versions/0009_economic_ledger_core.py"


class EconomicLedgerSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("economic_ledger_migration", MIGRATION_PATH)
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)
        cls.sql = "\n".join(cls.migration.UPGRADE_SQL)

    def test_migration_is_single_linear_forward_successor(self):
        scripts = ScriptDirectory.from_config(Config(str(INI)))
        self.assertEqual(scripts.get_heads(), ["0009_economic_ledger_core"])
        self.assertEqual((self.migration.revision, self.migration.down_revision),
                         ("0009_economic_ledger_core", "0008_usage_event_acl_hardening"))
        self.assertEqual(len(scripts.get_revisions("heads")), 1)
        self.assertIsNone(self.migration.downgrade.__annotations__.get("return"))
        downgrade = inspect.getsource(self.migration.downgrade)
        self.assertIn("pass", downgrade)
        self.assertNotIn("op.execute", downgrade)

    def test_four_relations_only_and_numeric_domain(self):
        names = [t.name for t in (supplier_funding_authorities, economic_receipts, ledger_accounts,
                                  ledger_transactions, ledger_entries)]
        self.assertEqual(names, ["supplier_funding_authorities", "economic_receipts", "ledger_accounts",
                                 "ledger_transactions", "ledger_entries"])
        self.assertIsInstance(economic_receipts.c.economic_receipt_id.type, UUID)
        self.assertIsInstance(economic_receipts.c.assessment_key.type, BYTEA)
        self.assertEqual((economic_receipts.c.computed_usage_cost_usd.type.precision,
                          economic_receipts.c.computed_usage_cost_usd.type.scale), (50, 18))
        self.assertEqual((ledger_entries.c.amount.type.precision, ledger_entries.c.amount.type.scale), (50, 18))
        self.assertEqual(economic_receipts.c.currency.type.length, 3)

    def test_funding_authority_is_versioned_opaque_and_receipt_bound(self):
        authority_fks = {c.name: tuple(c.columns.keys()) for c in economic_receipts.constraints
                         if isinstance(c, ForeignKeyConstraint)}
        self.assertEqual(authority_fks["fk_economic_receipts_funding_authority"],
                         ("funding_authority_id", "funding_authority_version", "funding_authority_digest"))
        self.assertEqual(tuple(supplier_funding_authorities.primary_key.columns.keys()),
                         ("funding_authority_id", "authority_version"))
        checks = {c.name: str(c.sqltext) for c in supplier_funding_authorities.constraints
                  if isinstance(c, CheckConstraint)}
        self.assertIn("JOUS_GLOBAL", checks["ck_supplier_funding_authorities_scope"])
        self.assertIn("ORGANIZATION", checks["ck_supplier_funding_authorities_scope"])
        self.assertIn("CUSTOMER_DIRECT", checks["ck_supplier_funding_authorities_bearer"])
        self.assertIn("CUSTOMER", checks["ck_supplier_funding_authorities_direct_customer"])
        self.assertNotIn("secret", set(supplier_funding_authorities.columns.keys()))
        self.assertIn("canonical_evidence", self.sql)
        self.assertIn("authority_digest=pg_catalog.sha256", self.sql)
        self.assertIn("supplier_funding_authority_immutable", self.sql)
        self.assertIn("route_decision_funding_authority_guard", self.sql)
        self.assertIn("funding_authority_version", economic_receipts.columns)
        self.assertIn("funding_authority_digest", economic_receipts.columns)

    def test_receipt_source_and_supersession_are_composite(self):
        foreign_keys = {c.name: (tuple(c.columns.keys()), tuple(e.target_fullname for e in c.elements))
                        for c in economic_receipts.constraints if isinstance(c, ForeignKeyConstraint)}
        self.assertIn("fk_economic_receipts_usage_binding", foreign_keys)
        self.assertEqual(foreign_keys["fk_economic_receipts_usage_binding"][0],
                         ("usage_event_id", "execution_id", "task_id", "organization_id",
                          "project_id", "actor_user_id", "dispatch_claim_id"))
        self.assertIn("fk_economic_receipts_supersession_binding", foreign_keys)
        unique = {c.name: tuple(c.columns.keys()) for c in economic_receipts.constraints
                  if isinstance(c, UniqueConstraint)}
        self.assertEqual(unique["uq_economic_receipts_assessment_key"], ("assessment_key",))
        self.assertEqual(unique["uq_economic_receipts_single_successor"], ("supersedes_receipt_id",))

    def test_receipt_status_and_null_zero_contract(self):
        checks = {c.name: str(c.sqltext) for c in economic_receipts.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("COMPUTED", checks["ck_economic_receipts_status"])
        self.assertIn("JOUS_BORNE", checks["ck_economic_receipts_bearer"])
        amount_state = checks["ck_economic_receipts_amount_state"]
        self.assertIn("provider_usage_cost_usd IS NOT NULL", amount_state)
        self.assertIn("assessment_status<>'COMPUTED'", amount_state)
        self.assertIn("computed_usage_cost_usd=provider_usage_cost_usd+provider_request_fee_usd+gateway_request_fee_usd", amount_state)
        self.assertIn("numeric(50,18)", self.sql)

    def test_ledger_keys_deferred_source_binding_and_append_only_acl(self):
        transaction_fks = [f for f in ledger_entries.constraints if isinstance(f, ForeignKeyConstraint)]
        source_fk = next(f for f in transaction_fks if f.name == "fk_ledger_entries_transaction_binding")
        self.assertTrue(source_fk.deferrable)
        self.assertEqual(source_fk.initially, "DEFERRED")
        self.assertEqual(tuple(source_fk.columns.keys()), ("ledger_transaction_id", "organization_id", "currency"))
        checks = {c.name: str(c.sqltext) for c in ledger_entries.constraints if isinstance(c, CheckConstraint)}
        self.assertIn("amount>0", checks["ck_ledger_entries_positive"])
        self.assertIn("DEBIT", checks["ck_ledger_entries_direction"])
        for table in (economic_receipts, ledger_transactions, ledger_entries):
            self.assertFalse(any(c.name == "updated_at" for c in table.columns))
        self.assertIn("DEFERRABLE INITIALLY DEFERRED", self.sql)
        self.assertIn("LANGUAGE plpgsql SECURITY INVOKER", self.sql)
        self.assertNotRegex(self.sql, r"(?i)SECURITY\s+DEFINER")

    def test_processor_is_preprovisioned_and_runtime_gets_no_economic_writes(self):
        self.assertNotRegex(self.sql, r"(?im)^\s*CREATE\s+ROLE\b")
        self.assertIn("Economic processor role attributes or membership are unsafe", self.sql)
        self.assertIn("REVOKE ALL PRIVILEGES ON TABLE public.economic_receipts", self.sql)
        self.assertIn("TO jous_economic_processor", self.sql)
        self.assertIn("jous_runtime", self.sql)
        self.assertIn("FORCE ROW LEVEL SECURITY", self.sql)
        self.assertIn("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE", self.sql)

    def test_processor_usage_event_select_allowlist_is_exactly_cost_inputs_plus_source(self):
        expected = {"usage_event_id", "organization_id", "project_id", "actor_user_id", "task_id",
            "dispatch_claim_id", "execution_id", "supplier_id", "input_tokens", "output_tokens", "route_decision_id",
            "usage_status", "evidence_sha256", "observed_at"}
        self.assertEqual(ECONOMIC_PROCESSOR_USAGE_COLUMNS, expected)
        grant = next(s for s in self.migration.UPGRADE_SQL
                     if s.startswith("GRANT SELECT (") and "ON public.usage_events TO jous_economic_processor" in s)
        granted = grant.split("GRANT SELECT (", 1)[1].split(") ON", 1)[0].split(",")
        self.assertEqual(set(granted), expected)
        self.assertNotIn("GRANT SELECT ON public.usage_events TO jous_economic_processor", self.sql)

    def test_journal_semantics_bind_posting_to_receipt(self):
        self.assertIn("COMPUTED_JOUS_COST_V1", self.sql)
        self.assertIn("cost_bearer<>'JOUS_BORNE'", self.sql)
        self.assertIn("computed_usage_cost_usd<=0", self.sql)
        self.assertIn("provider_lines<>provider_amount", self.sql)
        self.assertIn("gateway_lines<>gateway_amount", self.sql)
        self.assertIn("accrual_lines<>r.computed_usage_cost_usd", self.sql)
        self.assertIn("debits<>credits", self.sql)
        self.assertIn("Entries must precede immutable transaction header", self.sql)

    def test_computed_receipt_amounts_are_recalculated_from_immutable_evidence(self):
        function = next(s for s in self.migration.UPGRADE_SQL
                        if s.startswith("CREATE FUNCTION public.validate_economic_receipt_source"))
        self.assertIn("input_tokens,output_tokens", function)
        self.assertIn("u.input_tokens::numeric * p.input_price_per_1m", function)
        self.assertIn("u.output_tokens::numeric * p.output_price_per_1m", function)
        self.assertIn("* 0.000001::numeric", function)
        self.assertIn("expected_provider_usage", function)
        self.assertIn("NEW.provider_usage_cost_usd IS DISTINCT FROM expected_provider_usage", function)
        self.assertIn("NEW.provider_request_fee_usd IS DISTINCT FROM expected_provider_fee", function)
        self.assertIn("NEW.gateway_request_fee_usd IS DISTINCT FROM expected_gateway_fee", function)
        self.assertIn("Economic receipt amounts differ from exact UsageEvent/pricing calculation", function)
        self.assertIn("LANGUAGE plpgsql SECURITY INVOKER", function)

    def test_source_type_stays_immutable(self):
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertEqual(ast.literal_eval(next(n.value for n in ast.parse(source).body
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "revision")),
            "0009_economic_ledger_core")
