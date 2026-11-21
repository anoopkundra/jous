"""Offline source-contract checks for V1.3A migration 0005."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

from jous_api.route_economics import PricingVersion, RouteVersion
from jous_api.route_economics_validation import (
    EXPECTED_CONSTRAINTS, EXPECTED_POLICIES, POLICY_SOURCE, TABLES, _source_check_asts,
    _economic_funding_check_ast,
    validate_source_route_pricing,
)
from jous_api.product_runtime_validation import canonical_check_expression
from jous_api.database import PRODUCT_STATE_CHECK, ROUTE_ECONOMICS_STATE_CHECK
from jous_api.product_policy_canonicalization import (
    _Parser, _tokens, canonical_policy_expression,
)


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "services/api/migrations/versions/0005_route_economics.py"
HARDENING_PATH = ROOT / "services/api/migrations/versions/0006_snapshot_binding.py"
SPEC = importlib.util.spec_from_file_location("route_economics_migration", MIGRATION_PATH)
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)
HARDENING_SPEC = importlib.util.spec_from_file_location("route_decision_snapshot_hardening", HARDENING_PATH)
HARDENING = importlib.util.module_from_spec(HARDENING_SPEC)
HARDENING_SPEC.loader.exec_module(HARDENING)


class RouteEconomicsMigrationTests(unittest.TestCase):
    def setUp(self):
        self.sql = "\n".join(MIGRATION.UPGRADE_SQL)

    def test_v14c_funding_binding_is_additive_and_checked_by_successor_validator(self):
        migration_path = ROOT / "services/api/migrations/versions/0009_economic_ledger_core.py"
        source = migration_path.read_text(encoding="utf-8")
        for fragment in (
            "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_id uuid",
            "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_version integer",
            "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_digest bytea",
            "route_decision_funding_authority_guard",
            "Persisted RouteDecision funding binding is immutable",
        ):
            self.assertIn(fragment, source)
        self.assertIsNotNone(_economic_funding_check_ast())

    def test_revision_parent_and_exact_three_tables(self):
        self.assertEqual(MIGRATION.revision, "0005_route_economics")
        self.assertLessEqual(len(MIGRATION.revision), 32)
        self.assertEqual(MIGRATION.down_revision, "0004_product_acl_hardening")
        self.assertEqual(self.sql.count("CREATE TABLE public."), 3)
        for table in ("route_pricing_versions", "route_pricing_revocations", "route_decisions"):
            self.assertIn("CREATE TABLE public." + table, self.sql)
        self.assertNotIn("model_catalog", self.sql)
        self.assertNotIn("route_catalog", self.sql)

    def test_0006_is_a_single_constraint_only_forward_hardening(self):
        self.assertEqual(HARDENING.revision, "0006_snapshot_binding")
        self.assertEqual(HARDENING.down_revision, "0005_route_economics")
        self.assertEqual(HARDENING.UPGRADE_SQL.count("ALTER TABLE"), 1)
        self.assertIn("ALTER TABLE public.route_decisions", HARDENING.UPGRADE_SQL)
        self.assertEqual(HARDENING.UPGRADE_SQL.count("CONSTRAINT"), 2)
        self.assertIn(") IS TRUE", HARDENING.SNAPSHOT_BINDING_PREDICATE)
        self.assertEqual(len(re.findall(r"\bAND\b", HARDENING.SNAPSHOT_BINDING_PREDICATE)), 11)
        self.assertNotIn("CREATE", HARDENING.UPGRADE_SQL)
        self.assertNotIn("GRANT", HARDENING.UPGRADE_SQL)


    # Exact pg_get_expr outputs captured from the disposable PostgreSQL 17.11
    # migration database. Whitespace and redundant groups are retained here as
    # catalog evidence; canonicalization must preserve every policy predicate.
    CATALOG = {
        "jous_route_decisions_insert": """((EXISTS ( SELECT 1
   FROM tasks t
  WHERE ((t.id = route_decisions.task_id) AND (t.organization_id = route_decisions.organization_id) AND (t.project_id = route_decisions.project_id) AND (t.actor_user_id = route_decisions.actor_user_id) AND (t.dispatch_claim_id = route_decisions.dispatch_claim_id)))) AND (EXISTS ( SELECT 1
   FROM route_pricing_versions p
  WHERE (((p.pricing_version_id)::text = (route_decisions.pricing_version_id)::text) AND ((p.route_id)::text = (route_decisions.selected_route_id)::text) AND (p.route_version = route_decisions.selected_route_version) AND ((p.service_tier)::text = (route_decisions.service_tier)::text) AND ((p.currency)::text = (route_decisions.currency)::text) AND ((p.billing_basis)::text = (route_decisions.billing_basis)::text)))))""",
        "jous_route_decisions_select": """(EXISTS ( SELECT 1
   FROM tasks t
  WHERE ((t.id = route_decisions.task_id) AND (t.organization_id = route_decisions.organization_id) AND (t.project_id = route_decisions.project_id) AND (t.actor_user_id = route_decisions.actor_user_id) AND (t.dispatch_claim_id = route_decisions.dispatch_claim_id))))""",
        "jous_route_pricing_select": """(((pricing_status)::text = 'approved'::text) AND (NOT (EXISTS ( SELECT 1
   FROM route_pricing_revocations r
  WHERE ((r.pricing_version_id)::text = (route_pricing_versions.pricing_version_id)::text)))))""",
        "jous_route_revocations_select": "true",
    }

    @staticmethod
    def canonical(name, expression):
        return canonical_policy_expression(expression, policy_name=name)

    def test_every_migration_policy_source_matches_postgres17_catalog_ast(self):
        migration_policies=set(re.findall(r"\bCREATE POLICY\s+([A-Za-z0-9_]+)", self.sql))
        self.assertEqual(migration_policies, set(EXPECTED_POLICIES))
        self.assertEqual(set(POLICY_SOURCE), migration_policies)
        self.assertEqual(set(self.CATALOG), set(EXPECTED_POLICIES))
        for name in sorted(EXPECTED_POLICIES):
            with self.subTest(policy=name):
                self.assertEqual(self.canonical(name, POLICY_SOURCE[name]),
                                 self.canonical(name, self.CATALOG[name]))

    def test_boolean_and_negated_exists_semantics_are_explicit(self):
        self.assertEqual(self.canonical("jous_route_revocations_select", "true"),
                         ("BOOLEAN", True))
        self.assertNotEqual(self.canonical("jous_route_revocations_select", "true"),
                            self.canonical("jous_route_revocations_select", "false"))
        pricing = POLICY_SOURCE["jous_route_pricing_select"]
        not_exists = _Parser(_tokens(pricing), policy_name="jous_route_pricing_select").parse()
        exists = _Parser(_tokens(pricing.replace("NOT EXISTS", "EXISTS")),
                         policy_name="jous_route_pricing_select").parse()
        self.assertNotEqual(not_exists, exists)
        with self.assertRaises(ValueError):
            self.canonical("jous_route_pricing_select", pricing.replace("NOT EXISTS", "EXISTS"))
        self.assertEqual(self.canonical("jous_route_pricing_select", pricing)[1][1][0], "NOT")

    def test_pricing_correlation_and_decision_bindings_are_preserved(self):
        pricing = POLICY_SOURCE["jous_route_pricing_select"]
        with self.assertRaises(ValueError):
            self.canonical("jous_route_pricing_select", pricing.replace(
                "r.pricing_version_id", "r.route_id"))

        source = POLICY_SOURCE["jous_route_decisions_select"]
        expected = self.canonical("jous_route_decisions_select", source)
        with self.assertRaises(ValueError):
            self.canonical("jous_route_decisions_select", source.replace(
            "t.organization_id=route_decisions.organization_id",
            "t.organization_id<>route_decisions.organization_id"))
        for changed in (
            source.replace("t.project_id=route_decisions.project_id",
                           "t.project_id=route_decisions.organization_id"),
            source.replace("t.actor_user_id=route_decisions.actor_user_id",
                           "t.actor_user_id=route_decisions.project_id"),
            source.replace("t.dispatch_claim_id=route_decisions.dispatch_claim_id",
                           "t.dispatch_claim_id=route_decisions.actor_user_id"),
            source.replace(" AND t.project_id=route_decisions.project_id", ""),
        ):
            with self.subTest(expression=changed):
                with self.assertRaises(ValueError):
                    self.canonical("jous_route_decisions_select", changed)

    def test_policy_scope_alias_boolean_and_unsupported_syntax_fail_closed(self):
        insert = POLICY_SOURCE["jous_route_decisions_insert"]
        expected_insert = self.canonical("jous_route_decisions_insert", insert)
        select = self.canonical("jous_route_decisions_select",
                                POLICY_SOURCE["jous_route_decisions_select"])
        self.assertNotEqual(select, expected_insert)
        with self.assertRaises(ValueError):
            self.canonical("jous_route_decisions_insert", insert.replace(" AND ", " OR ", 1))
        for changed in (
            insert.replace("public.tasks", "private.tasks"),
            insert.replace("public.tasks t WHERE", "public.tasks x WHERE"),
            insert.replace("=route_decisions.dispatch_claim_id", "::uuid=route_decisions.dispatch_claim_id"),
            insert.replace("EXISTS (SELECT 1", "evil (SELECT 1", 1),
        ):
            with self.subTest(expression=changed):
                with self.assertRaises(ValueError):
                    self.canonical("jous_route_decisions_insert", changed)

    def test_migration_guards_existing_revision_roles_and_task_binding(self):
        for part in ("0004_product_acl_hardening", "jous_runtime", "jous_security_reader",
                     "uq_tasks_execution_binding", "ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE"):
            self.assertIn(part, self.sql)
        self.assertIn("current_user <> 'postgres'", self.sql)

    def test_no_extension_default_privilege_or_security_definer(self):
        upper = self.sql.upper()
        self.assertNotIn("CREATE EXTENSION", upper)
        self.assertNotIn("ALTER DEFAULT PRIVILEGES", upper)
        self.assertNotIn("SECURITY DEFINER", upper)
        self.assertNotIn("GRANT ALL", upper)

    def test_prices_are_resolved_immutably_and_revocations_are_append_only_to_runtime(self):
        self.assertIn("provider_fee_applicable", self.sql)
        self.assertIn("gateway_fee_applicable", self.sql)
        self.assertIn("fee_basis_verified", self.sql)
        self.assertIn("pricing_status <> 'approved' OR (fee_basis_verified AND", self.sql)
        self.assertIn("provider_request_fee_usd IS NOT NULL", self.sql)
        self.assertIn("gateway_request_fee_usd IS NOT NULL", self.sql)
        self.assertIn("GRANT SELECT (pricing_version_id) ON public.route_pricing_revocations TO jous_runtime", self.sql)
        self.assertNotIn("GRANT INSERT", self.sql[self.sql.index("route_pricing_revocations"):self.sql.index("CREATE TABLE public.route_decisions")])

    def test_overlap_guard_uses_half_open_intervals_and_deterministic_lock(self):
        self.assertIn("pg_catalog.hashtextextended", self.sql)
        self.assertIn("pg_catalog.pg_advisory_xact_lock(lock_key)", self.sql)
        self.assertIn("NEW.effective_from < p.valid_until AND p.effective_from < NEW.valid_until", self.sql)
        self.assertIn("p.pricing_status='approved'", self.sql)
        self.assertIn("CREATE TRIGGER trg_route_price_interval BEFORE INSERT", self.sql)
        self.assertIn("pg_catalog.jsonb_build_array(NEW.route_id,NEW.route_version,NEW.service_tier,NEW.currency,NEW.billing_basis)", self.sql)

    def test_rls_force_policies_column_grants_and_owner_only_acl(self):
        for table in ("route_pricing_versions", "route_pricing_revocations", "route_decisions"):
            self.assertIn(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY", self.sql)
            self.assertIn(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY", self.sql)
        for policy in ("jous_route_pricing_select", "jous_route_revocations_select",
                       "jous_route_decisions_select", "jous_route_decisions_insert"):
            self.assertIn("CREATE POLICY " + policy, self.sql)
        self.assertIn("uq_tasks_execution_binding", self.sql)
        self.assertIn("fk_route_decisions_task_binding", self.sql)
        self.assertIn("fk_route_decisions_pricing", self.sql)
        self.assertIn("decision_snapshot text NOT NULL", self.sql)
        self.assertIn("octet_length(decision_snapshot) BETWEEN 1 AND 65536", self.sql)
        self.assertIn("octet_length(snapshot_sha256)=32", self.sql)
        self.assertIn("pg_catalog.sha256(pg_catalog.convert_to(decision_snapshot,'UTF8'))", self.sql)
        self.assertIn("PRIMARY KEY (task_id)", self.sql)
        self.assertIn("UNIQUE (dispatch_claim_id)", self.sql)
        self.assertIn("REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %s", self.sql)
        self.assertIn("REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM %s", self.sql)
        self.assertNotIn("CASCADE", self.sql)

    def test_acl_hardening_handles_owner_public_and_arbitrary_grantees_safely(self):
        self.assertIn("x.grantee<>target.relowner", self.sql)
        self.assertIn("x.grantee<>target.relowner", self.sql)
        self.assertIn("IF grantee_oid=0 THEN grantee_sql := 'PUBLIC'", self.sql)
        self.assertIn("pg_catalog.quote_ident(grantee_name::text)", self.sql)
        self.assertIn("Missing relation ACL grantee", self.sql)
        self.assertIn("Missing column ACL grantee", self.sql)
        self.assertIn("rolname IN ('postgres','jous_runtime','jous_security_reader')", self.sql)
        self.assertNotIn("rolname IN ('anon'", self.sql)
        self.assertIn("Non-owner relation ACL remains", self.sql)
        self.assertIn("Unexpected route-economics column ACL remains", self.sql)
        self.assertIn("IF grantee_oid=0 THEN grantee_sql := 'PUBLIC'", self.sql)

    def test_runtime_grants_are_column_scoped_and_have_no_write_authority_on_prices(self):
        self.assertIn("GRANT SELECT (pricing_version_id,route_id,route_version,service_tier", self.sql)
        self.assertIn("GRANT SELECT (pricing_version_id) ON public.route_pricing_revocations TO jous_runtime", self.sql)
        self.assertIn("GRANT INSERT (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id", self.sql)
        self.assertNotIn("GRANT INSERT (", self.sql[self.sql.index("GRANT SELECT (pricing_version_id,route_id"):self.sql.index("GRANT SELECT (pricing_version_id) ON public.route_pricing_revocations")])
        self.assertNotIn("GRANT SELECT ON TABLE", self.sql)
        self.assertNotIn("GRANT INSERT ON TABLE", self.sql)
        self.assertNotIn("GRANT UPDATE", self.sql)
        self.assertNotIn("GRANT DELETE", self.sql)

    def test_no_v1_2_migration_source_was_modified_by_this_contract(self):
        for old in range(1, 5):
            self.assertFalse((ROOT / f"services/api/migrations/versions/000{old}_route_economics.py").exists())
        self.assertTrue((ROOT / "services/api/migrations/versions/0004_product_relation_acl_hardening.py").exists())

    def test_successor_validator_contract_is_additive_and_source_route_bound(self):
        self.assertEqual(TABLES, {"route_pricing_versions", "route_pricing_revocations", "route_decisions"})
        self.assertEqual(len(EXPECTED_POLICIES), 4)
        self.assertIn("fk_route_decisions_task_binding", EXPECTED_CONSTRAINTS["route_decisions"])
        route = RouteVersion(
            route_id="hf-qwen3-32b-deepinfra-v1", version=1, logical_model_id="jous.text.general.v1",
            logical_model_version=1, supplier_id="hugging_face", supplier_native_model_id="Qwen/Qwen3-32B:deepinfra",
            underlying_provider="DeepInfra", route_kind="direct", gateway_id=None, provider_selection="direct",
            service_tier="standard", capabilities=("text_generation",), context_capacity=32768,
            operational_enabled=False, admission_authorized=False, token_authority_status="unresolved",
            route_authority_id="source-route-v1",
        )
        price = PricingVersion(
            pricing_version_id="historical-price-v1", route_id=route.route_id, route_version=1,
            service_tier="standard", currency="USD", input_price_per_1m="1", output_price_per_1m="2",
            provider_request_fee="0", gateway_request_fee=None, gateway_fee_applicable=False,
            fee_basis_verified=True, source_type="manual_review", source_evidence_id="historical-evidence-v1",
            reviewed_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
            effective_from=datetime(2026, 11, 16, tzinfo=timezone.utc),
            valid_until=datetime(2027, 11, 16, tzinfo=timezone.utc),
            status="approved",
        )
        self.assertTrue(validate_source_route_pricing(route, price))
        self.assertFalse(route.operational_enabled)
        self.assertFalse(route.admission_authorized)
        check_tokens = _source_check_asts()
        self.assertEqual(len(check_tokens), 19)
        self.assertIn(("route_decisions", "ck_route_decisions_snapshot_digest"), check_tokens)

    def test_v12_revision_gate_remains_default_and_0005_has_explicit_successor_gate(self):
        self.assertIn("0004_product_acl_hardening", PRODUCT_STATE_CHECK)
        self.assertNotIn("0005_route_economics", PRODUCT_STATE_CHECK)
        self.assertIn("0006_snapshot_binding", ROUTE_ECONOMICS_STATE_CHECK)
        self.assertNotIn("0005_route_economics", ROUTE_ECONOMICS_STATE_CHECK)
        self.assertNotIn("0004_product_acl_hardening", ROUTE_ECONOMICS_STATE_CHECK)

    def test_true_only_check_wrapper_is_scoped_to_snapshot_binding_profile(self):
        source = "(decision_snapshot::jsonb->>'decision_version'=decision_version AND decision_snapshot::jsonb->'selected'->>'currency'=currency) IS TRUE"
        expected = canonical_check_expression(source, "route_decisions",
            "ck_route_decisions_snapshot_binding", route_economics=True)
        self.assertIsNotNone(expected)
        self.assertEqual(expected[0], "IS_TRUE")
        default_ast = canonical_check_expression(source, "route_decisions",
            "ck_route_decisions_snapshot_binding")
        self.assertNotEqual(default_ast, expected)
        unrelated_profile_ast = canonical_check_expression(source, "route_decisions",
            "ck_route_decisions_identity", route_economics=True)
        self.assertNotEqual(unrelated_profile_ast, expected)

    def test_postgres17_check_deparse_is_semantic_and_v13_scoped(self):
        canonical=lambda value,name='ck_route_pricing_currency': canonical_check_expression(
            value,'route_pricing_versions',name,route_economics=True)

        # Exact observed catalog coercions: varchar/text casts and parser-added
        # grouping preserve the source comparison's operands and operator.
        self.assertEqual(canonical("currency='USD'"),
                         canonical("(currency)::text = 'USD'::text"))
        self.assertNotEqual(canonical("currency='USD'"),canonical("currency='EUR'"))
        self.assertEqual(canonical("source_type IN ('a','b')",'ck_route_pricing_source'),
                         canonical("((source_type)::text = ANY ((ARRAY['a'::character varying, "
                                    "'b'::character varying])::text[]))",'ck_route_pricing_source'))
        self.assertNotEqual(canonical("source_type IN ('a','b')",'ck_route_pricing_source'),
                            canonical("((source_type)::text = ANY ((ARRAY['a'::character varying, "
                                      "'c'::character varying])::text[]))",'ck_route_pricing_source'))
        self.assertIsNone(canonical("((source_type)::text = ANY ((ARRAY['a'::text, "
                                    "'b'::text])::varchar[]))",'ck_route_pricing_source'))

        self.assertEqual(canonical('x BETWEEN 0 AND 10','ck_route_pricing_rates'),
                         canonical('(x >= 0 AND x <= 10)','ck_route_pricing_rates'))
        self.assertNotEqual(canonical('x BETWEEN 0 AND 10','ck_route_pricing_rates'),
                            canonical('(x > 0 AND x <= 10)','ck_route_pricing_rates'))
        self.assertNotEqual(canonical('x >= 0','ck_route_pricing_rates'),
                            canonical('x > 0','ck_route_pricing_rates'))
        self.assertEqual(canonical('(a AND b)','ck_route_pricing_rates'),
                         canonical('(((a) AND (b)))','ck_route_pricing_rates'))
        self.assertNotEqual(canonical('a AND b','ck_route_pricing_rates'),
                            canonical('a OR b','ck_route_pricing_rates'))

        # The PostgreSQL-specific profile is explicit and cannot be applied to
        # V1.2 or an unrelated table/constraint.
        self.assertNotEqual(canonical_check_expression(
            "(currency)::text = 'USD'::text",'route_pricing_versions','ck_route_pricing_currency'),
            canonical_check_expression("currency='USD'",'route_pricing_versions','ck_route_pricing_currency'))
        self.assertIsNone(canonical_check_expression(
            "(currency)::text = 'USD'::text",'tasks','ck_route_pricing_currency',route_economics=True))

    def test_all_postgres17_v13_check_catalog_fixtures_match_source_asts(self):
        # Exact CHECK catalog outputs captured from the disposable PostgreSQL
        # 17.11 database. These fixtures target the observed representation
        # differences while the disposable full validator remains separately gated.
        from jous_api.product_runtime_validation import canonical_check_expression
        sources=_source_check_asts()
        fixtures={
            ('route_pricing_versions','ck_route_pricing_currency'):
                "((currency)::text = 'USD'::text)",
            ('route_pricing_versions','ck_route_pricing_source'):
                "((source_type)::text = ANY ((ARRAY['provider_published'::character varying, "
                "'gateway_published'::character varying, 'invoice_review'::character varying, "
                "'manual_review'::character varying])::text[]))",
            ('route_decisions','ck_route_decisions_token_bounds'):
                "(((input_token_bound >= 0) AND (input_token_bound <= 2147483647)) AND "
                "((output_allowance >= 0) AND (output_allowance <= 2147483647)))",
            ('route_pricing_versions','ck_route_pricing_approval'):
                "(((pricing_status)::text = ANY ((ARRAY['pending'::character varying, "
                "'approved'::character varying])::text[])) AND (((pricing_status)::text <> "
                "'approved'::text) OR (fee_basis_verified AND ((provider_fee_applicable AND "
                "(provider_request_fee_usd IS NOT NULL)) OR ((NOT provider_fee_applicable) AND "
                "(provider_request_fee_usd IS NULL))) AND ((gateway_fee_applicable AND "
                "(gateway_request_fee_usd IS NOT NULL)) OR ((NOT gateway_fee_applicable) AND "
                "(gateway_request_fee_usd IS NULL))))))",
        }
        for (table,name),catalog_expression in fixtures.items():
            with self.subTest(table=table,constraint=name):
                self.assertEqual(
                    canonical_check_expression(catalog_expression,table,name,route_economics=True),
                    sources[(table,name)])


if __name__ == "__main__":
    unittest.main()
