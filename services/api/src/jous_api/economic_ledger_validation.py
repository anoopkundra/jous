"""Fail-closed catalog checks for the V1.4C economic schema/security profile."""
from sqlalchemy import text

from .database import DatabaseUnavailable
from .economic_models import (supplier_funding_authorities, economic_receipts,
                              ledger_accounts, ledger_transactions, ledger_entries)
from .usage_event_validation import _canonical_type_signature
from .task_models import EXECUTION_COLUMNS, EXECUTION_INSERT_COLUMNS


_TABLES = (supplier_funding_authorities, economic_receipts, ledger_accounts,
           ledger_transactions, ledger_entries)
_RELATIONS = """SELECT c.relname::text,pg_catalog.pg_get_userbyid(c.relowner)::text,c.relkind::text,
 c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN
 ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries') ORDER BY c.relname"""
_COLUMNS = """SELECT c.relname::text,a.attname::text,pg_catalog.format_type(a.atttypid,a.atttypmod),
 a.attnotnull,pg_catalog.pg_get_expr(d.adbin,d.adrelid) FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
 LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
 WHERE n.nspname='public' AND c.relname IN
 ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum"""
_CONSTRAINTS = """SELECT c.relname::text,k.conname::text,k.contype::text,k.convalidated,
 k.condeferrable,k.condeferred FROM pg_catalog.pg_constraint k
 JOIN pg_catalog.pg_class c ON c.oid=k.conrelid JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN
 ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')"""
_POLICIES = """SELECT c.relname::text,p.polname::text,p.polcmd::text,p.polpermissive,
 ARRAY(SELECT r.rolname::text FROM pg_catalog.pg_roles r WHERE r.oid=ANY(p.polroles) ORDER BY r.rolname),
 pg_catalog.pg_get_expr(p.polqual,p.polrelid),pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)
 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 AND c.relname IN ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries','executions')
 AND (c.relname<>'executions' OR p.polname='jous_executions_economic_processor_select')"""
_TRIGGERS = """SELECT t.tgname::text,p.prosecdef,p.proconfig FROM pg_catalog.pg_trigger t
 JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' AND c.relname IN
 ('supplier_funding_authorities','route_decisions','executions','economic_receipts','ledger_transactions','ledger_entries') AND NOT t.tgisinternal"""

_EXPECTED_POLICIES = {
    ("supplier_funding_authorities", "supplier_funding_authorities_runtime_select", "r"),
    ("supplier_funding_authorities", "supplier_funding_authorities_processor_select", "r"),
    ("executions", "jous_executions_economic_processor_select", "r"),
    ("economic_receipts", "jous_economic_receipts_processor_select", "r"),
    ("economic_receipts", "jous_economic_receipts_processor_insert", "a"),
    ("ledger_accounts", "jous_ledger_accounts_processor_select", "r"),
    ("ledger_transactions", "jous_ledger_transactions_processor_select", "r"),
    ("ledger_transactions", "jous_ledger_transactions_processor_insert", "a"),
    ("ledger_entries", "jous_ledger_entries_processor_select", "r"),
    ("ledger_entries", "jous_ledger_entries_processor_insert", "a"),
}
_INSERT_COLUMNS = {
    "economic_receipts": {"economic_receipt_id","organization_id","project_id","actor_user_id","task_id",
        "dispatch_claim_id","execution_id","usage_event_id","route_decision_id","pricing_version_id",
        "funding_authority_id","funding_authority_version","funding_authority_digest",
        "economic_policy_version","treatment_policy_digest","calculation_version","assessment_status",
        "cost_bearer","currency","provider_usage_cost_usd","provider_request_fee_usd",
        "gateway_request_fee_usd","computed_usage_cost_usd","pricing_snapshot_canonical",
        "pricing_snapshot_sha256","source_usage_digest","supersedes_receipt_id","observed_at"},
    "ledger_transactions": {"ledger_transaction_id","organization_id","economic_receipt_id","posting_purpose","currency","source_digest"},
    "ledger_entries": {"ledger_transaction_id","organization_id","line_number","ledger_account_id","currency","direction","amount"},
}


async def validate_economic_ledger_catalog(connection):
    """Check the four immutable relations, processor boundary, and trigger posture."""
    try:
        relations = (await connection.execute(text(_RELATIONS))).all()
        if [(r[0],r[1],r[2],bool(r[3]),bool(r[4])) for r in relations] != [
                (t.name,"postgres","r",True,True) for t in sorted(_TABLES,key=lambda x:x.name)]:
            raise ValueError()
        expected = {}
        for table in _TABLES:
            for column in table.columns:
                from sqlalchemy.dialects.postgresql import dialect
                expected[(table.name,column.name)] = (
                    _canonical_type_signature(column.type.compile(dialect=dialect())),
                    not column.nullable,
                    "statement_timestamp" if column.server_default is not None else None)
        actual = {}
        for table,column,type_name,not_null,default in (await connection.execute(text(_COLUMNS))).all():
            actual[(table,column)] = (_canonical_type_signature(type_name),bool(not_null),
                                      "statement_timestamp" if default and "statement_timestamp" in default else None)
        if actual != expected:
            raise ValueError()
        expected_constraints = {t.name:{c.name for c in t.constraints} for t in _TABLES}
        expected_constraints["ledger_entries"].add("ledger_entries_balance")
        expected_constraints["ledger_transactions"].add("ledger_transactions_balance")
        constraints = {t.name:set() for t in _TABLES}
        for table,name,kind,validated,deferrable,deferred in (await connection.execute(text(_CONSTRAINTS))).all():
            if not validated:
                raise ValueError()
            constraints[table].add(name)
            deferred_names = {"fk_ledger_entries_transaction_binding","ledger_entries_balance",
                              "ledger_transactions_balance"}
            if (name in deferred_names and not (deferrable and deferred)) or (
                    name not in deferred_names and (deferrable or deferred)):
                raise ValueError()
        if constraints != expected_constraints:
            raise ValueError()
        policies = (await connection.execute(text(_POLICIES))).all()
        policy_set = {(r[0],r[1],r[2].decode() if isinstance(r[2],bytes) else r[2]) for r in policies}
        if policy_set != _EXPECTED_POLICIES:
            raise ValueError()
        for table,name,command,permissive,roles,using,check in policies:
            command = command.decode() if isinstance(command,bytes) else command
            expected_role = ("jous_runtime",) if name == "supplier_funding_authorities_runtime_select" else ("jous_economic_processor",)
            if not permissive or tuple(roles) != expected_role:
                raise ValueError()
            if command == "r":
                normalized = (using or "").lower().replace(" ", "")
                if name == "supplier_funding_authorities_runtime_select":
                    if ("jous_global" not in normalized or "organization_id" not in normalized or
                            "current_setting" not in normalized or "jous.organization_id" not in normalized):
                        raise ValueError()
                elif (using or "").strip().lower() != "true":
                    normalized_using = (using or "").lower().replace(" ", "")
                    if name != "jous_executions_economic_processor_select" or not all(
                            token in normalized_using for token in
                            ("exists", "fromusage_eventsu", "u.execution_id=executions.id",
                             "u.task_id=executions.task_id")):
                        raise ValueError()
            if command == "a" and not check:
                raise ValueError()
        triggers = (await connection.execute(text(_TRIGGERS))).all()
        if {r[0] for r in triggers} != {
                "route_decision_funding_authority_guard", "supplier_funding_authority_immutable",
                "executions_credential_authority_guard",
                "economic_receipts_source_guard","ledger_transactions_source_guard",
                "ledger_entries_before_insert","ledger_entries_balance","ledger_transactions_balance"}:
            raise ValueError()
        if any(definer or "search_path=pg_catalog" not in (config or []) for _,definer,config in triggers):
            raise ValueError()
        execution_contract_result = await connection.execute(text("""SELECT
          pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
          EXISTS (SELECT 1 FROM pg_catalog.pg_constraint k WHERE k.conrelid=c.oid
            AND k.conname='ck_executions_credential_authority_ref' AND k.contype='c' AND k.convalidated)
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
          WHERE n.nspname='public' AND c.relname='executions' AND a.attname='credential_authority_ref'
            AND a.attnum>0 AND NOT a.attisdropped"""))
        execution_contract = execution_contract_result.one_or_none()
        if execution_contract is None or tuple(execution_contract) != ("character varying(255)", False, True):
            raise ValueError()
        role = await connection.execute(text("""SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,
          rolcreaterole,rolreplication,rolinherit FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'"""))
        if tuple(role.one()) != (True,False,False,False,False,False,False):
            raise ValueError()
        if await connection.scalar(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m
          WHERE m.member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor')
             OR (m.roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor')
                 AND (m.member<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
                      OR m.inherit_option OR m.set_option)))
          OR EXISTS (SELECT 1 FROM pg_catalog.pg_class c WHERE c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'))
          OR EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'))
          OR EXISTS (SELECT 1 FROM pg_catalog.pg_proc p WHERE p.proowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'))""")):
            raise ValueError()
        acls = (await connection.execute(text("""SELECT c.relname::text,a.grantee,a.privilege_type,a.is_grantable
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
          LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
          WHERE n.nspname='public' AND c.relname IN ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')
          AND a.grantee<>c.relowner"""))).all()
        processor_oid = await connection.scalar(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'"))
        expected_relation_acl = {(table,"SELECT") for table in ("economic_receipts","ledger_accounts","ledger_transactions","ledger_entries")}
        if {(r[0],r[2]) for r in acls if r[1]==processor_oid and not r[3]} != expected_relation_acl or any(r[1]!=processor_oid or r[2]!="SELECT" or r[3] for r in acls):
            raise ValueError()
        if await connection.scalar(text("""SELECT EXISTS (SELECT 1 FROM (VALUES ('anon'),('authenticated'),
          ('service_role'),('jous_runtime'),('jous_security_reader')) r(name)
          CROSS JOIN (VALUES ('supplier_funding_authorities'),('economic_receipts'),('ledger_accounts'),('ledger_transactions'),('ledger_entries')) t(name)
          CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(priv)
          WHERE pg_catalog.has_table_privilege(r.name,'public.'||t.name,p.priv))""")):
            raise ValueError()
        for role_name in ("jous_runtime", "jous_economic_processor"):
            if await connection.scalar(text("SELECT pg_catalog.has_table_privilege(:role,'public.supplier_funding_authorities','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')"),
                                       {"role":role_name}):
                raise ValueError()
        processor_execution_columns = {"id","task_id","organization_id","project_id","actor_user_id",
                                       "dispatch_claim_id","request_started_at","credential_authority_ref"}
        runtime_execution_select_columns = set(EXECUTION_COLUMNS)
        runtime_execution_insert_columns = set(EXECUTION_INSERT_COLUMNS)
        exec_columns = (await connection.execute(text("""SELECT attname::text FROM pg_catalog.pg_attribute
          WHERE attrelid='public.executions'::regclass AND attnum>0 AND NOT attisdropped"""))).scalars()
        for column in exec_columns:
            for role_name, allowed_select, allowed_insert in (
                    ("jous_runtime", runtime_execution_select_columns, runtime_execution_insert_columns),
                    ("jous_economic_processor", processor_execution_columns, set())):
                selected = await connection.scalar(text("SELECT pg_catalog.has_column_privilege(:role,'public.executions',:column,'SELECT')"),
                                                   {"role":role_name,"column":column})
                inserted = await connection.scalar(text("SELECT pg_catalog.has_column_privilege(:role,'public.executions',:column,'INSERT')"),
                                                   {"role":role_name,"column":column})
                mutated = await connection.scalar(text("SELECT pg_catalog.has_column_privilege(:role,'public.executions',:column,'UPDATE,REFERENCES')"),
                                                  {"role":role_name,"column":column})
                if bool(selected) != (column in allowed_select) or bool(inserted) != (column in allowed_insert) or mutated:
                    raise ValueError()
        runtime_authority_columns = {"funding_authority_id","authority_version","scope","organization_id",
                                     "supplier_id","route_id","route_version","credential_authority_ref",
                                     "authority_digest"}
        processor_authority_columns = {"funding_authority_id","authority_version","scope","organization_id",
            "supplier_id","route_id","route_version","credential_authority_ref","account_owner",
            "cost_bearer","evidence_type","evidence_reference","effective_at","canonical_evidence","authority_digest"}
        for column in supplier_funding_authorities.columns.keys():
            for role_name, allowed in (("jous_runtime",runtime_authority_columns),
                                       ("jous_economic_processor",processor_authority_columns)):
                actual_select = await connection.scalar(text("SELECT pg_catalog.has_column_privilege(:role,:table,:column,'SELECT')"),
                                                        {"role":role_name,"table":"public.supplier_funding_authorities","column":column})
                if actual_select is not (column in allowed):
                    raise ValueError()
                if await connection.scalar(text("SELECT pg_catalog.has_column_privilege(:role,:table,:column,'INSERT,UPDATE,REFERENCES')"),
                                           {"role":role_name,"table":"public.supplier_funding_authorities","column":column}):
                    raise ValueError()
        for table in _TABLES:
            columns = set(table.columns.keys())
            for column in columns:
                expected_insert = column in _INSERT_COLUMNS.get(table.name,set())
                if await connection.scalar(text("SELECT pg_catalog.has_column_privilege('jous_economic_processor',:table,:column,'INSERT')"),
                                           {"table":"public."+table.name,"column":column}) != expected_insert:
                    raise ValueError()
        if await connection.scalar(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl d
          CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
          WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
          AND d.defaclobjtype='r' AND d.defaclnamespace IN (0,(SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='public'))
          AND a.grantee IN (0,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
           (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
           (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'),
           (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'),
           (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_security_reader'),
           (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor')))""")):
            raise ValueError()
    except Exception:
        raise DatabaseUnavailable("Economic ledger database safety check failed") from None
