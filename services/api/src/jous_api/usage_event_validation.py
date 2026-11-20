"""Fail-closed V1.4B UsageEvent catalog and runtime-authority validation."""
import re
from sqlalchemy import text

from .database import DatabaseUnavailable
from .route_economics_validation import validate_route_economics_runtime
from .usage_event_models import usage_events


REVISION = "0008_usage_event_acl_hardening"
TABLE_SQL = """SELECT pg_catalog.pg_get_userbyid(c.relowner)::text,c.relkind::text,
 c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname='usage_events'"""
COLUMN_SQL = """SELECT a.attname::text,pg_catalog.format_type(a.atttypid,a.atttypmod),
 a.attnotnull,pg_catalog.pg_get_expr(d.adbin,d.adrelid)
 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_catalog.pg_attrdef d
 ON d.adrelid=c.oid AND d.adnum=a.attnum
 WHERE n.nspname='public' AND c.relname='usage_events' AND a.attnum>0 AND NOT a.attisdropped
 ORDER BY a.attnum"""
CONSTRAINT_SQL = """SELECT conname::text,contype::text,condeferrable,convalidated
 FROM pg_catalog.pg_constraint WHERE conrelid='public.usage_events'::regclass"""
POLICY_SQL = """SELECT polname::text,polcmd::text,polpermissive,
 ARRAY(SELECT rolname::text FROM pg_catalog.pg_roles WHERE oid=ANY(polroles) ORDER BY rolname),
 pg_catalog.pg_get_expr(polqual,polrelid),pg_catalog.pg_get_expr(polwithcheck,polrelid)
 FROM pg_catalog.pg_policy WHERE polrelid='public.usage_events'::regclass ORDER BY polname"""
RELATION_ACL_SQL = """SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
 LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
 WHERE n.nspname='public' AND c.relname='usage_events' AND a.grantee<>c.relowner"""
COLUMN_ACL_SQL = """SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute x ON x.attrelid=c.oid,LATERAL pg_catalog.aclexplode(x.attacl) a
 WHERE n.nspname='public' AND c.relname='usage_events' AND x.attnum>0 AND NOT x.attisdropped
 AND (a.is_grantable OR a.grantee<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'))"""
DEFAULT_ACL_SQL = """SELECT count(*) FROM pg_catalog.pg_default_acl d
 CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
 WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
 AND d.defaclobjtype='r' AND d.defaclnamespace IN
 (0,(SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='public'))
 AND a.grantee IN (0,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
 (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
 (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'))"""
ROLE_RELATION_AUTHORITY_SQL = """SELECT count(*) FROM
 (VALUES ('anon'),('authenticated'),('service_role'),('jous_runtime'),('jous_security_reader')) r(name)
 CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),
 ('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(privilege)
 WHERE pg_catalog.has_table_privilege(r.name,'public.usage_events',p.privilege)"""
PRIVILEGE_SQL = """SELECT a.attname::text,
 pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'SELECT'),
 pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'INSERT'),
 pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'UPDATE'),
 pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,'REFERENCES'),
 pg_catalog.has_column_privilege('jous_security_reader',c.oid,a.attnum,'SELECT'),
 pg_catalog.has_column_privilege('jous_security_reader',c.oid,a.attnum,'INSERT')
 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
 WHERE n.nspname='public' AND c.relname='usage_events' AND a.attnum>0 AND NOT a.attisdropped
 ORDER BY a.attnum"""
INDEX_SQL = """SELECT i.relname::text FROM pg_catalog.pg_index x
 JOIN pg_catalog.pg_class i ON i.oid=x.indexrelid
 WHERE x.indrelid='public.usage_events'::regclass"""


def _expected_columns():
    result = {}
    from sqlalchemy.dialects.postgresql import dialect as pg_dialect
    dialect = pg_dialect()
    for column in usage_events.columns:
        result[column.name] = (column.type.compile(dialect=dialect), not column.nullable,
                              str(column.server_default.arg) if column.server_default is not None else None)
    return result


_TYPE_ALIASES = {
    "uuid": "uuid", "bool": "boolean", "boolean": "boolean",
    "int2": "smallint", "smallint": "smallint",
    "int4": "integer", "int": "integer", "integer": "integer",
    "int8": "bigint", "bigint": "bigint",
    "float4": "real", "real": "real", "float8": "double precision",
    "double precision": "double precision", "bytea": "bytea", "text": "text",
    "timestamp with time zone": "timestamptz", "timestamptz": "timestamptz",
    "timestamp without time zone": "timestamp", "timestamp": "timestamp",
    "time with time zone": "timetz", "timetz": "timetz",
    "time without time zone": "time", "time": "time",
}


def _canonical_type_signature(type_name):
    """Normalize known PostgreSQL type aliases, preserving modifiers exactly."""
    original = " ".join(str(type_name).strip().split())
    value = original.lower()
    is_array = value.endswith("[]")
    while value.endswith("[]"):
        value = value[:-2].rstrip()
    match = re.fullmatch(
        r"(character varying|varchar|character|char|numeric|decimal)\s*\((\d+)(?:\s*,\s*(\d+))?\)", value)
    if match:
        base, first, second = match.groups()
        if base in {"character varying", "varchar"}:
            signature = ("varchar", int(first))
        elif base in {"character", "char"}:
            signature = ("char", int(first))
        else:
            signature = ("numeric", int(first), int(second or 0))
    elif value in {"character varying", "varchar"}:
        signature = ("varchar", None)
    elif value in {"character", "char"}:
        signature = ("char", None)
    elif value in {"numeric", "decimal"}:
        signature = ("numeric", None, None)
    else:
        alias = _TYPE_ALIASES.get(value)
        signature = (alias,) if alias is not None else ("opaque", original)
    return ("array", signature) if is_array else signature


def _types_equivalent(expected, actual):
    return _canonical_type_signature(expected) == _canonical_type_signature(actual)


def _expected_constraints():
    from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
    return {constraint.name: ("c" if isinstance(constraint, CheckConstraint) else
            "f" if isinstance(constraint, ForeignKeyConstraint) else
            "p" if isinstance(constraint, PrimaryKeyConstraint) else "u")
            for constraint in usage_events.constraints}


def _policy_is_bounded(name, using, check):
    compact = " ".join((using or check or "").lower().split())
    if name.endswith("_select"):
        return (using is not None and check is None and "tasks t" in compact
                and "executions e" in compact and "dispatch_claim_id" in compact)
    return (using is None and check is not None and "tasks t" in compact
            and "executions e" in compact and "organization_memberships m" in compact
            and "role" in compact and "owner" in compact and "dispatch_claim_id" in compact
            and "route_decisions d" in compact and "selected_route_version" in compact
            and "route_decision_id" in compact and "jsonb_strip_nulls" in compact
            and "jsonb_build_object" in compact and "usage_status" in compact)


async def validate_usage_event_runtime(connection, *, stage_observer=None):
    """Run frozen V1.2/V1.3 validators, then exact additive UsageEvent checks."""
    try:
        await validate_route_economics_runtime(connection, expected_revision=REVISION,
                                               usage_events=True, stage_observer=stage_observer)
        relation = (await connection.execute(text(TABLE_SQL))).one_or_none()
        if relation != ("postgres", "r", True, True):
            raise ValueError()
        columns = {name: (sql_type, bool(not_null), " ".join(default.split()) if default else None)
                   for name, sql_type, not_null, default in
                   (await connection.execute(text(COLUMN_SQL))).all()}
        expected = _expected_columns()
        if set(columns) != set(expected):
            raise ValueError()
        for name, (sql_type, not_null, default) in expected.items():
            actual_type, actual_not_null, actual_default = columns[name]
            if not _types_equivalent(sql_type, actual_type) or actual_not_null != not_null:
                raise ValueError()
            if name == "recorded_at":
                if not actual_default or "statement_timestamp" not in actual_default:
                    raise ValueError()
            elif actual_default is not None:
                raise ValueError()
        constraints = {}
        for name, kind, deferrable, validated in (await connection.execute(text(CONSTRAINT_SQL))).all():
            if deferrable or not validated:
                raise ValueError()
            constraints[name] = kind
        if constraints != _expected_constraints():
            raise ValueError()
        policies = (await connection.execute(text(POLICY_SQL))).all()
        if len(policies) != 2:
            raise ValueError()
        for name, command, permissive, roles, using, check in policies:
            if (name not in {"jous_usage_events_select", "jous_usage_events_insert"}
                    or not permissive or tuple(roles) != ("jous_runtime",)
                    or command != ("r" if name.endswith("_select") else "a")
                    or not _policy_is_bounded(name, using, check)):
                raise ValueError()
        if await connection.scalar(text(RELATION_ACL_SQL)) != 0:
            raise ValueError()
        if await connection.scalar(text(DEFAULT_ACL_SQL)) != 0:
            raise ValueError()
        if await connection.scalar(text(ROLE_RELATION_AUTHORITY_SQL)) != 0:
            raise ValueError()
        if await connection.scalar(text(COLUMN_ACL_SQL)) != 0:
            raise ValueError()
        privileges = (await connection.execute(text(PRIVILEGE_SQL))).all()
        if len(privileges) != len(usage_events.columns):
            raise ValueError()
        for name, select, insert, update, references, reader_select, reader_insert in privileges:
            expected_insert = name != "recorded_at"
            if (select, insert, update, references, reader_select, reader_insert) != (
                    True, expected_insert, False, False, False, False):
                raise ValueError()
        if set((await connection.execute(text(INDEX_SQL))).scalars()) != {
                "pk_usage_events", "uq_usage_events_source_identity",
                "uq_usage_events_single_successor", "uq_usage_events_binding",
                "ix_usage_events_project_recorded"}:
            raise ValueError()
    except Exception:
        raise DatabaseUnavailable("Usage-event database safety check failed") from None


async def validate_current_product_runtime(connection, *, stage_observer=None):
    """Require the exact schema revision needed by this application build."""
    try:
        revisions = (await connection.execute(text(
            "SELECT version_num::text FROM public.alembic_version ORDER BY version_num"))).scalars().all()
        if revisions != [REVISION]:
            raise ValueError()
        return await validate_usage_event_runtime(connection, stage_observer=stage_observer)
    except Exception:
        raise DatabaseUnavailable("Product database revision is not supported") from None
