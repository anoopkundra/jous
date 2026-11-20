"""Additive V1.3 route-economics contract checks; source admission stays authoritative."""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
import re
import sys
from contextlib import contextmanager
from time import perf_counter

from sqlalchemy import text

from .database import DatabaseUnavailable
from .product_policy_canonicalization import canonical_policy_expression
from .product_runtime_validation import (canonical_check_expression, _check_tokens,
                                         validate_route_economics_product_runtime)
from .route_economics import PricingVersion, RouteVersion
from .runtime_resolution import catalog_resolution
from jous_supply.registry import resolve as resolve_source_route


EXPECTED_REVISION = "0006_snapshot_binding"
TABLES = {"route_pricing_versions", "route_pricing_revocations", "route_decisions"}
EXPECTED_COLUMNS = {
    "route_pricing_versions": {
        "pricing_version_id": "character varying(255)", "route_id": "character varying(255)",
        "route_version": "integer", "service_tier": "character varying(255)", "currency": "character varying(3)",
        "billing_basis": "character varying(64)", "input_price_per_1m": "numeric(20,12)",
        "output_price_per_1m": "numeric(20,12)", "provider_fee_applicable": "boolean",
        "provider_request_fee_usd": "numeric(20,12)", "gateway_fee_applicable": "boolean",
        "gateway_request_fee_usd": "numeric(20,12)", "fee_basis_verified": "boolean",
        "source_type": "character varying(32)", "source_evidence_id": "character varying(255)",
        "reviewed_at": "timestamp with time zone", "effective_from": "timestamp with time zone",
        "valid_until": "timestamp with time zone", "pricing_status": "character varying(16)",
        "created_at": "timestamp with time zone",
    },
    "route_pricing_revocations": {
        "pricing_version_id": "character varying(255)", "revoked_at": "timestamp with time zone",
        "reason_code": "character varying(64)", "evidence_id": "character varying(255)",
    },
    "route_decisions": {
        "task_id": "uuid", "organization_id": "uuid", "project_id": "uuid", "actor_user_id": "uuid",
        "dispatch_claim_id": "uuid", "decision_version": "character varying(255)",
        "selector_version": "character varying(255)", "logical_model_id": "character varying(255)",
        "logical_model_version": "integer", "decided_at": "timestamp with time zone",
        "pricing_version_id": "character varying(255)", "selected_route_id": "character varying(255)",
        "selected_route_version": "integer", "service_tier": "character varying(255)",
        "currency": "character varying(3)", "billing_basis": "character varying(64)",
        "input_token_bound": "integer", "output_allowance": "integer", "estimated_cost_usd": "numeric(38,18)",
        "decision_snapshot": "text", "snapshot_sha256": "bytea", "created_at": "timestamp with time zone",
    },
}
EXPECTED_CONSTRAINTS = {
    "route_pricing_versions": {"pk_route_pricing_versions", "uq_route_pricing_identity",
        "ck_route_pricing_version_positive", "ck_route_pricing_currency", "ck_route_pricing_billing",
        "ck_route_pricing_rates", "ck_route_pricing_provider_fee", "ck_route_pricing_gateway_fee",
        "ck_route_pricing_approval", "ck_route_pricing_source", "ck_route_pricing_evidence"},
    "route_pricing_revocations": {"pk_route_pricing_revocations", "fk_route_pricing_revocation_version",
        "ck_route_pricing_revocation_fields"},
    "route_decisions": {"pk_route_decisions", "uq_route_decisions_dispatch_claim",
        "fk_route_decisions_task_binding", "fk_route_decisions_pricing", "ck_route_decisions_snapshot",
        "ck_route_decisions_snapshot_binding",
        "ck_route_decisions_hash", "ck_route_decisions_snapshot_digest", "ck_route_decisions_currency",
        "ck_route_decisions_route_version", "ck_route_decisions_token_bounds", "ck_route_decisions_estimate",
        "ck_route_decisions_identity"},
}
EXPECTED_INDEXES = {"pk_route_pricing_versions", "uq_route_pricing_identity", "ix_route_pricing_lookup",
                    "ix_route_pricing_source_time", "pk_route_pricing_revocations", "pk_route_decisions",
                    "uq_route_decisions_dispatch_claim", "ix_route_decisions_project_time"}
EXPECTED_POLICIES = {
    "jous_route_pricing_select": ("route_pricing_versions", "r", ("jous_runtime",)),
    "jous_route_revocations_select": ("route_pricing_revocations", "r", ("jous_runtime",)),
    "jous_route_decisions_select": ("route_decisions", "r", ("jous_runtime",)),
    "jous_route_decisions_insert": ("route_decisions", "a", ("jous_runtime",)),
}

REVISION_SQL = "SELECT version_num::text FROM public.alembic_version"
TABLE_SQL = """SELECT c.relname::text,pg_catalog.pg_get_userbyid(c.relowner)::text,c.relkind::text,
 c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND (left(c.relname,6)='route_' OR c.relname IN ('model_catalog','route_catalog'))"""
COLUMN_SQL = """SELECT c.relname::text,a.attname::text,pg_catalog.format_type(a.atttypid,a.atttypmod),
 a.attnotnull,pg_catalog.pg_get_expr(d.adbin,d.adrelid) FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
 LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
 WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum"""
CONSTRAINT_SQL = """SELECT c.relname::text,k.conname::text,k.contype::text,k.condeferrable,k.convalidated
 FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')"""
CHECK_EXPRESSION_SQL = """SELECT c.relname::text,k.conname::text,
 pg_catalog.pg_get_expr(k.conbin,k.conrelid),k.convalidated
 FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
 AND k.contype='c'"""
KEY_CONSTRAINT_SQL = """SELECT c.relname::text,k.conname::text,k.contype::text,rc.relname::text,
 ARRAY(SELECT a.attname::text FROM unnest(k.conkey) WITH ORDINALITY x(attnum,ord)
       JOIN pg_catalog.pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=x.attnum ORDER BY x.ord),
 ARRAY(SELECT a.attname::text FROM unnest(k.confkey) WITH ORDINALITY x(attnum,ord)
       JOIN pg_catalog.pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=x.attnum ORDER BY x.ord),
 k.confdeltype::text,k.confupdtype::text,k.condeferrable,k.condeferred
 FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
 LEFT JOIN pg_catalog.pg_class rc ON rc.oid=k.confrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
 AND k.contype IN ('p','u','f')"""
INDEX_SQL = """SELECT i.relname::text FROM pg_catalog.pg_index x
 JOIN pg_catalog.pg_class i ON i.oid=x.indexrelid JOIN pg_catalog.pg_class t ON t.oid=x.indrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public'
 AND t.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')"""
POLICY_SQL = """SELECT c.relname::text,p.polname::text,p.polcmd::text,p.polpermissive,
 ARRAY(SELECT r.rolname::text FROM pg_catalog.pg_roles r WHERE r.oid=ANY(p.polroles) ORDER BY r.rolname),
 pg_catalog.pg_get_expr(p.polqual,p.polrelid),pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)
 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')"""
TRIGGER_SQL = """SELECT t.tgname::text,pg_catalog.pg_get_triggerdef(t.oid,true),p.proname::text,
 l.lanname::text,p.prosecdef,p.proconfig,pg_catalog.pg_get_functiondef(p.oid)
 FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
 JOIN pg_catalog.pg_language l ON l.oid=p.prolang WHERE n.nspname='public'
 AND c.relname='route_pricing_versions' AND NOT t.tgisinternal"""
RELATION_ACL_SQL = """SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
 LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
 WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
 AND a.grantee<>c.relowner"""
COLUMN_ACL_SQL = """SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute x ON x.attrelid=c.oid,LATERAL pg_catalog.aclexplode(x.attacl) a
 WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
 AND x.attnum>0 AND NOT x.attisdropped AND
 (a.is_grantable OR a.grantee<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'))"""
POLICY_SOURCE = {
    "jous_route_pricing_select": "pricing_status='approved' AND NOT EXISTS (SELECT 1 FROM public.route_pricing_revocations r WHERE r.pricing_version_id=route_pricing_versions.pricing_version_id)",
    "jous_route_revocations_select": "true",
    "jous_route_decisions_select": "EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=route_decisions.task_id AND t.organization_id=route_decisions.organization_id AND t.project_id=route_decisions.project_id AND t.actor_user_id=route_decisions.actor_user_id AND t.dispatch_claim_id=route_decisions.dispatch_claim_id)",
    "jous_route_decisions_insert": "EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=route_decisions.task_id AND t.organization_id=route_decisions.organization_id AND t.project_id=route_decisions.project_id AND t.actor_user_id=route_decisions.actor_user_id AND t.dispatch_claim_id=route_decisions.dispatch_claim_id) AND EXISTS (SELECT 1 FROM public.route_pricing_versions p WHERE p.pricing_version_id=route_decisions.pricing_version_id AND p.route_id=route_decisions.selected_route_id AND p.route_version=route_decisions.selected_route_version AND p.service_tier=route_decisions.service_tier AND p.currency=route_decisions.currency AND p.billing_basis=route_decisions.billing_basis)",
}


def validate_source_route_pricing(route: RouteVersion, pricing: PricingVersion) -> bool:
    """Match price evidence to source-owned identity; never grants admission."""
    try:
        source = resolve_source_route(route.logical_model_id, route.route_id)
    except Exception:
        return False
    return (
        (pricing.route_id, pricing.route_version, pricing.service_tier) ==
        (route.route_id, route.version, route.service_tier)
        and (source.logical_model_id, source.supplier_id, source.supplier_native_model_id, source.underlying_provider) ==
        (route.logical_model_id, route.supplier_id, route.supplier_native_model_id, route.underlying_provider)
    )


def _squash(value: str | None) -> str | None:
    return re.sub(r"\s+", " ", value).strip() if value is not None else None


def validate_route_economics_policy_rows(rows):
    """Validate exact V1.3 policy metadata and source/catalog semantic ASTs."""
    policies = {}
    for table, name, command, permissive, roles, using, check in rows:
        if name in policies:
            raise ValueError()
        using_ast = canonical_policy_expression(using, policy_name=name) if using is not None else None
        check_ast = canonical_policy_expression(check, policy_name=name) if check is not None else None
        policies[name] = (table, command, bool(permissive), tuple(roles), using_ast, check_ast)
    if set(policies) != set(EXPECTED_POLICIES):
        raise ValueError()
    for name, (table, command, roles) in EXPECTED_POLICIES.items():
        source_ast = canonical_policy_expression(POLICY_SOURCE[name], policy_name=name)
        expected = (table, command, True, roles,
                    source_ast if command == "r" else None,
                    source_ast if command == "a" else None)
        if policies[name] != expected:
            raise ValueError()


@lru_cache(maxsize=1)
def _source_check_asts():
    """Read literal upgrade DDL as data; never import or execute the migration."""
    migration_path = Path(__file__).resolve().parents[4] / "services/api/migrations/versions/0005_route_economics.py"
    tree = ast.parse(migration_path.read_text(encoding="utf-8"), filename=str(migration_path))
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "UPGRADE_SQL" for target in node.targets))
    statements = ast.literal_eval(assignment.value)
    expected = {}
    for statement in statements:
        table_match = re.search(r"CREATE TABLE public\.([A-Za-z0-9_]+)", statement, re.IGNORECASE)
        if not table_match:
            continue
        table = table_match.group(1)
        for match in re.finditer(r"CONSTRAINT\s+([A-Za-z0-9_]+)\s+CHECK\s*\(", statement, re.IGNORECASE):
            start = match.end()
            index = start
            depth = 1
            quoted = False
            while index < len(statement) and depth:
                char = statement[index]
                if quoted:
                    if char == "'":
                        if index + 1 < len(statement) and statement[index + 1] == "'":
                            index += 2
                            continue
                        quoted = False
                elif char == "'":
                    quoted = True
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                index += 1
            if depth or quoted:
                raise ValueError()
            name = match.group(1)
            source_expression = statement[start:index - 1]
            signature = canonical_check_expression(source_expression, table, name,
                                                   route_economics=True)
            if signature is None or (table, name) in expected:
                raise ValueError(f"Unsupported or duplicate V1.3 check constraint {table}.{name}")
            expected[(table, name)] = tuple(signature)
    if not expected:
        raise ValueError()
    hardening_path = migration_path.with_name("0006_snapshot_binding.py")
    hardening_tree = ast.parse(hardening_path.read_text(encoding="utf-8"), filename=str(hardening_path))
    hardening_assignment = next(node for node in hardening_tree.body if isinstance(node, ast.Assign)
                                and any(isinstance(target, ast.Name)
                                        and target.id == "SNAPSHOT_BINDING_PREDICATE"
                                        for target in node.targets))
    hardening_expression = ast.literal_eval(hardening_assignment.value)
    hardening_signature = canonical_check_expression(
        hardening_expression, "route_decisions", "ck_route_decisions_snapshot_binding",
        route_economics=True)
    if hardening_signature is None:
        raise ValueError("Unsupported hardened snapshot-binding CHECK")
    expected[("route_decisions", "ck_route_decisions_snapshot_binding")] = tuple(hardening_signature)
    return expected


@contextmanager
def _stage(observer, name):
    started = perf_counter()
    try:
        yield
    finally:
        if observer:
            error = sys.exc_info()[1]
            try:
                observer(name, perf_counter() - started, type(error).__name__ if error else None)
            except Exception:
                pass


async def validate_route_economics_runtime(connection, *, stage_observer=None):
    """Validate V1.3 additions after the unchanged V1.2 product validator.

    V1.3 CHECK constraints use the existing fail-closed CHECK AST with its
    opt-in, constraint-bounded PostgreSQL catalog coercions. Policy expressions
    remain exact whitespace-normalized comparisons until the existing policy
    parser can prove any observed catalog representation equivalent.
    """
    try:
        await validate_route_economics_product_runtime(
            connection, stage_observer=stage_observer)
        async with catalog_resolution(connection):
            with _stage(stage_observer, "ROUTE_ECONOMICS_REVISION"):
                if await connection.scalar(text(REVISION_SQL)) != EXPECTED_REVISION:
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_TABLES"):
                rows = (await connection.execute(text(TABLE_SQL))).all()
                if {row[0] for row in rows} != TABLES or any(
                    row[1] != "postgres" or row[2] != "r" or not row[3] or not row[4] for row in rows
                ):
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_COLUMNS"):
                columns = {table: {} for table in TABLES}
                for table, column, sql_type, not_null, default in (await connection.execute(text(COLUMN_SQL))).all():
                    columns[table][column] = (sql_type, bool(not_null), _squash(default))
                if {table: set(values) for table, values in columns.items()} != {table: set(values) for table, values in EXPECTED_COLUMNS.items()}:
                    raise ValueError()
                for table, values in columns.items():
                    for name, (sql_type, not_null, default) in values.items():
                        expected_type = EXPECTED_COLUMNS[table][name]
                        expected_not_null = name not in {"provider_request_fee_usd", "gateway_request_fee_usd"}
                        if (sql_type, not_null) != (expected_type, expected_not_null):
                            raise ValueError()
                        if name in {"created_at", "revoked_at"} and "statement_timestamp" not in (default or ""):
                            raise ValueError()
                        if name not in {"created_at", "revoked_at"} and default is not None:
                            raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_CONSTRAINTS"):
                actual = {table: set() for table in TABLES}
                for table, name, kind, deferrable, validated in (await connection.execute(text(CONSTRAINT_SQL))).all():
                    if deferrable or not validated:
                        raise ValueError()
                    actual[table].add(name)
                if actual != EXPECTED_CONSTRAINTS:
                    raise ValueError()
                key_rows = (await connection.execute(text(KEY_CONSTRAINT_SQL))).all()
                keys = {(table, name): (kind, target, tuple(local or ()), tuple(remote or ()),
                                         delete if kind == "f" else None, update if kind == "f" else None,
                                         bool(deferrable), bool(deferred))
                        for table, name, kind, target, local, remote, delete, update, deferrable, deferred in key_rows}
                required_keys = {
                    ("route_pricing_versions", "pk_route_pricing_versions"): ("p", None, ("pricing_version_id",), (), None, None, False, False),
                    ("route_pricing_versions", "uq_route_pricing_identity"): ("u", None, ("pricing_version_id", "route_id", "route_version", "service_tier", "currency", "billing_basis"), (), None, None, False, False),
                    ("route_pricing_revocations", "pk_route_pricing_revocations"): ("p", None, ("pricing_version_id",), (), None, None, False, False),
                    ("route_pricing_revocations", "fk_route_pricing_revocation_version"): ("f", "route_pricing_versions", ("pricing_version_id",), ("pricing_version_id",), "r", "r", False, False),
                    ("route_decisions", "pk_route_decisions"): ("p", None, ("task_id",), (), None, None, False, False),
                    ("route_decisions", "uq_route_decisions_dispatch_claim"): ("u", None, ("dispatch_claim_id",), (), None, None, False, False),
                    ("route_decisions", "fk_route_decisions_task_binding"): ("f", "tasks", ("task_id", "organization_id", "project_id", "actor_user_id", "dispatch_claim_id"), ("id", "organization_id", "project_id", "actor_user_id", "dispatch_claim_id"), "r", "r", False, False),
                    ("route_decisions", "fk_route_decisions_pricing"): ("f", "route_pricing_versions", ("pricing_version_id", "selected_route_id", "selected_route_version", "service_tier", "currency", "billing_basis"), ("pricing_version_id", "route_id", "route_version", "service_tier", "currency", "billing_basis"), "r", "r", False, False),
                }
                if any(keys.get(key) != value for key, value in required_keys.items()):
                    raise ValueError()
                check_expressions = {}
                for table, name, expression, validated in (await connection.execute(text(CHECK_EXPRESSION_SQL))).all():
                    signature = canonical_check_expression(expression, table, name,
                                                           route_economics=True)
                    if not validated or signature is None:
                        raise ValueError()
                    check_expressions[(table, name)] = tuple(signature)
                if check_expressions != _source_check_asts():
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_INDEXES"):
                if set((await connection.execute(text(INDEX_SQL))).scalars()) != EXPECTED_INDEXES:
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_POLICIES"):
                policy_rows = (await connection.execute(text(POLICY_SQL))).all()
                validate_route_economics_policy_rows(policy_rows)
            with _stage(stage_observer, "ROUTE_ECONOMICS_OVERLAP_GUARD"):
                triggers = (await connection.execute(text(TRIGGER_SQL))).all()
                if len(triggers) != 1:
                    raise ValueError()
                trigger_name, trigger_def, function_name, language, security_definer, config, function_def = triggers[0]
                function_source = str(function_def)
                if (trigger_name != "trg_route_price_interval" or function_name != "enforce_route_price_interval"
                        or language != "plpgsql" or security_definer
                        or "search_path=pg_catalog" not in (config or [])
                        or "hashtextextended" not in function_source
                        or "pg_advisory_xact_lock" not in function_source
                        or "effective_from" not in function_source or "valid_until" not in function_source
                        or "UPDATE" in str(trigger_def).upper() or "DELETE" in str(trigger_def).upper()):
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_ACLS"):
                if await connection.scalar(text(RELATION_ACL_SQL)) != 0 or await connection.scalar(text(COLUMN_ACL_SQL)) != 0:
                    raise ValueError()
            with _stage(stage_observer, "ROUTE_ECONOMICS_PRIVILEGES"):
                rows = (await connection.execute(text("""SELECT c.relname::text,a.attname::text,
                  pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'SELECT'),
                  pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'INSERT'),
                  pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'UPDATE'),
                  pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'REFERENCES'),
                  pg_catalog.has_column_privilege('jous_security_reader',c.oid,a.attnum,'SELECT'),
                  pg_catalog.has_column_privilege('jous_security_reader',c.oid,a.attnum,'INSERT')
                  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                  JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='public'
                    AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
                    AND a.attnum>0 AND NOT a.attisdropped"""))).all()
                if not rows:
                    raise ValueError()
                for table, column, select, insert, update, references, reader_select, reader_insert in rows:
                    expected_select = (table == "route_pricing_versions" or table == "route_pricing_revocations" and column == "pricing_version_id" or table == "route_decisions")
                    expected_insert = table == "route_decisions" and column != "created_at"
                    if (select, insert, update, references, reader_select, reader_insert) != (expected_select, expected_insert, False, False, False, False):
                        raise ValueError()
                forbidden = await connection.scalar(text("""SELECT NOT EXISTS (
                  SELECT 1 FROM (VALUES ('route_pricing_versions'),('route_pricing_revocations'),('route_decisions')) t(name)
                  CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name)
                  CROSS JOIN (VALUES ('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(priv)
                  WHERE pg_catalog.has_table_privilege(r.name,'public.'||t.name,p.priv))"""))
                if forbidden is not True:
                    raise ValueError()
                no_price_writes = await connection.scalar(text("""SELECT NOT EXISTS (
                  SELECT 1 FROM (VALUES ('route_pricing_versions'),('route_pricing_revocations')) t(name)
                  CROSS JOIN (VALUES ('INSERT'),('UPDATE'),('DELETE')) p(priv)
                  WHERE pg_catalog.has_table_privilege('jous_runtime','public.'||t.name,p.priv))"""))
                if no_price_writes is not True:
                    raise ValueError()
    except Exception:
        raise DatabaseUnavailable("Route-economics safety check failed") from None
