"""Opt-in disposable PostgreSQL tests for V1.4C source and journal invariants."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
ENABLED = os.environ.get("JOUS_V14C_DISPOSABLE_AUTHORIZED") == "YES"


def _urls():
    names = ("ADMIN", "RUNTIME", "PROCESSOR")
    values = [os.environ.get("JOUS_V14C_DISPOSABLE_" + n + "_URL", "") for n in names]
    parsed = [urlsplit(value) for value in values]
    if any(p.scheme != "postgresql" or p.hostname != "127.0.0.1" or not p.port
           or not p.path.startswith("/jous_v14c_step3_") or p.query or p.fragment for p in parsed):
        raise RuntimeError("Only the named loopback V1.4C disposable database is permitted")
    if [p.username for p in parsed] != ["postgres", "jous_runtime", "jous_economic_processor"]:
        raise RuntimeError("Disposable admin/runtime/processor identities must remain separate")
    if len({(p.hostname, p.port, p.path) for p in parsed}) != 1:
        raise RuntimeError("All test principals must use the same disposable database")
    return values


@unittest.skipUnless(ENABLED, "Explicit disposable PostgreSQL authorization required; never use managed Dev")
class EconomicLedgerPostgreSQLTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_url, cls.runtime_url, cls.processor_url = _urls()

        async def verify_target():
            import asyncpg
            admin = await asyncpg.connect(cls.admin_url)
            try:
                version = await admin.fetchval("SELECT current_setting('server_version')")
                sentinel = await admin.fetchval(
                    "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
                revision = await admin.fetchval("SELECT version_num FROM public.alembic_version")
                if not version.startswith("17.11") or sentinel != "JOUS_V14C_STEP3_DISPOSABLE_AUTHORIZED":
                    raise RuntimeError("Disposable PostgreSQL 17.11 sentinel check failed")
                if revision != "0009_economic_ledger_core":
                    raise RuntimeError("Disposable database must already be migrated through 0009")
            finally:
                await admin.close()
        asyncio.run(verify_target())

    async def test_economic_ledger_catalog_validator_passes_as_runtime(self):
        from sqlalchemy.engine import make_url
        from sqlalchemy.ext.asyncio import create_async_engine
        from jous_api.economic_ledger_validation import validate_economic_ledger_catalog

        engine = create_async_engine(make_url(self.runtime_url).set(
            drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
        try:
            async with engine.connect() as connection:
                await validate_economic_ledger_catalog(connection)
        finally:
            await engine.dispose()

    async def test_restricted_roles_source_binding_and_balanced_posting(self):
        import asyncpg
        from jous_api.usage_events import normalize_execution
        from test_route_decision_snapshot_binding_0006 import (
            BILLING_BASIS, INSERT_DECISION, create_task, exact_snapshot_bytes)

        admin = await asyncpg.connect(self.admin_url)
        runtime = await asyncpg.connect(self.runtime_url)
        processor = await asyncpg.connect(self.processor_url)
        try:
            self.assertEqual(await runtime.fetchval("SELECT current_user"), "jous_runtime")
            self.assertFalse(await runtime.fetchval("SELECT bool_or(has_table_privilege(current_user,'public.'||n,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')) FROM unnest(ARRAY['economic_receipts','ledger_accounts','ledger_transactions','ledger_entries']) n"))
            self.assertEqual(await processor.fetchval("SELECT current_user"), "jous_economic_processor")
            self.assertFalse(await processor.fetchval(
                "SELECT has_table_privilege(current_user,'public.usage_events','SELECT')"))
            self.assertTrue(await processor.fetchval(
                "SELECT has_column_privilege(current_user,'public.usage_events','supplier_id','SELECT')"))
            self.assertFalse(await processor.fetchval(
                "SELECT has_table_privilege(current_user,'public.usage_events','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')"))
            role = await processor.fetchrow("SELECT rolsuper,rolbypassrls,rolinherit,rolcreaterole FROM pg_roles WHERE rolname=current_user")
            self.assertEqual(tuple(role), (False, False, False, False))
            self.assertFalse(await processor.fetchval("SELECT pg_has_role(current_user,'postgres','MEMBER')"))
            self.assertFalse(await processor.fetchval("SELECT pg_has_role('jous_runtime','jous_economic_processor','MEMBER')"))
            self.assertFalse(await processor.fetchval("SELECT has_schema_privilege(current_user,'public','CREATE')"))
            self.assertFalse(await processor.fetchval("SELECT has_table_privilege(current_user,'public.supplier_funding_authorities','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')"))
            self.assertTrue(await processor.fetchval("SELECT has_column_privilege(current_user,'public.supplier_funding_authorities','cost_bearer','SELECT')"))
            self.assertFalse(await processor.fetchval("SELECT has_column_privilege(current_user,'public.supplier_funding_authorities','recorded_at','SELECT')"))
            self.assertFalse(await processor.fetchval("SELECT has_column_privilege(current_user,'public.supplier_funding_authorities','cost_bearer','INSERT')"))
            self.assertFalse(await runtime.fetchval("SELECT has_table_privilege(current_user,'public.supplier_funding_authorities','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')"))
            self.assertTrue(await runtime.fetchval("SELECT has_column_privilege(current_user,'public.supplier_funding_authorities','funding_authority_id','SELECT')"))
            self.assertFalse(await runtime.fetchval("SELECT has_column_privilege(current_user,'public.supplier_funding_authorities','cost_bearer','SELECT')"))
            self.assertTrue(await processor.fetchval("""SELECT bool_and(relrowsecurity AND relforcerowsecurity)
              FROM pg_class WHERE oid=ANY(ARRAY['public.economic_receipts'::regclass,
                'public.ledger_accounts'::regclass,'public.ledger_transactions'::regclass,
                'public.ledger_entries'::regclass])"""))
            for relation in ("economic_receipts", "ledger_accounts", "ledger_transactions", "ledger_entries"):
                self.assertFalse(await processor.fetchval("SELECT has_table_privilege(current_user,$1,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')", "public."+relation))
            for function in ("validate_economic_receipt_source", "prepare_ledger_transaction",
                             "validate_ledger_transaction", "guard_ledger_entry_insert"):
                self.assertFalse(await processor.fetchval("SELECT has_function_privilege(current_user,'public.'||$1||'()','EXECUTE')", function))
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("INSERT INTO public.ledger_accounts(ledger_account_id,account_code,economic_classification,normal_side,currency,postable,account_version) VALUES($1,'forged','FORGED','DEBIT','USD',true,1)", uuid4())
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("INSERT INTO public.supplier_funding_authorities(funding_authority_id) VALUES($1)", uuid4())
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute("INSERT INTO public.supplier_funding_authorities(funding_authority_id) VALUES($1)", uuid4())
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute("INSERT INTO public.economic_receipts(economic_receipt_id) VALUES($1)", uuid4())
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await runtime.fetch("SELECT * FROM public.economic_receipts")
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("SET ROLE postgres")
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("SET ROLE jous_runtime")
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("CREATE TABLE public.v14c_acl_probe(id integer)")

            user_id, org_id, project_id = uuid4(), uuid4(), uuid4()
            await admin.execute("INSERT INTO public.users(id) VALUES($1)", user_id)
            await admin.execute("INSERT INTO public.organizations(id,name) VALUES($1,'economic-ledger-test')", org_id)
            await admin.execute("INSERT INTO public.organization_memberships(id,user_id,organization_id,role) VALUES($1,$2,$3,'owner')", uuid4(), user_id, org_id)
            await admin.execute("INSERT INTO public.projects(id,organization_id,name) VALUES($1,$2,'economic-ledger-test')", project_id, org_id)
            now = datetime.now(timezone.utc)
            price_id = "v14c-test-" + uuid4().hex
            await admin.execute("""INSERT INTO public.route_pricing_versions
              (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,
               input_price_per_1m,output_price_per_1m,provider_fee_applicable,provider_request_fee_usd,
               gateway_fee_applicable,gateway_request_fee_usd,fee_basis_verified,source_type,
               source_evidence_id,reviewed_at,effective_from,valid_until,pricing_status)
              VALUES($1,'route-bind',1,'standard','USD',$2,1,1,true,0,false,NULL,true,
                'manual_review','evidence',$3::timestamptz,$3::timestamptz+interval '2 hours',
                $3::timestamptz+interval '3 hours','approved')""",
                price_id, BILLING_BASIS, now)
            task_id = await create_task(admin, user_id, org_id, project_id, uuid4())
            task_values = dict(await admin.fetchrow("SELECT * FROM public.tasks WHERE id=$1", task_id))
            if isinstance(task_values["request_parameters"], str):
                task_values["request_parameters"] = json.loads(task_values["request_parameters"])
            from types import SimpleNamespace
            task = SimpleNamespace(**task_values)
            snapshot = {"decision_version":"route-decision.v1","logical_model_id":"jous.text.general.v1",
                "logical_model_version":1,"selector_version":"economic.v0","decision_time":now.isoformat(),
                "input_token_bound":1,"output_allowance":1024,"selected":{"route_id":"route-bind",
                "route_version":1,"pricing_version_id":price_id,"estimated_cost":"0.123","currency":"USD"},
                "candidate_evaluations":[{"route_id":"route-bind"}]}
            snapshot_text = exact_snapshot_bytes(snapshot)
            authority_id = uuid4()
            authority_digest = await admin.fetchval("""WITH e AS (SELECT pg_catalog.jsonb_build_object(
              'schema_version','jous.supplier-funding-authority.v1','funding_authority_id',$1::uuid,
              'authority_version',1,'scope','JOUS_GLOBAL','organization_id',NULL,'supplier_id','local',
              'route_id','route-bind','route_version',1,'credential_authority_ref','fixture:jous-account',
              'account_owner','JOUS','cost_bearer','JOUS_BORNE','evidence_type','controlled_fixture',
              'evidence_reference','fixture:jous-funding','effective_at',pg_catalog.to_char(
                $2::timestamptz AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))::text AS canonical)
              INSERT INTO public.supplier_funding_authorities
              (funding_authority_id,authority_version,scope,organization_id,supplier_id,route_id,route_version,
               credential_authority_ref,account_owner,cost_bearer,evidence_type,evidence_reference,effective_at,
               canonical_evidence,authority_digest)
              SELECT $1,1,'JOUS_GLOBAL',NULL,'local','route-bind',1,'fixture:jous-account','JOUS',
                'JOUS_BORNE','controlled_fixture','fixture:jous-funding',$2,e.canonical,
                pg_catalog.sha256(pg_catalog.convert_to(e.canonical,'UTF8')) FROM e RETURNING authority_digest""",
              authority_id, now)
            funded_insert = INSERT_DECISION.replace(
                "decision_snapshot,snapshot_sha256)",
                "decision_snapshot,snapshot_sha256,funding_authority_id,funding_authority_version,funding_authority_digest)")
            funded_insert = funded_insert.replace("$9,$10)", "$9,$10,$11,$12,$13)")
            await admin.execute(funded_insert, task_id, org_id, project_id, user_id,
                task.dispatch_claim_id, now, price_id, BILLING_BASIS, snapshot_text,
                hashlib.sha256(snapshot_text.encode()).digest(), authority_id, 1, authority_digest)
            with self.assertRaises(asyncpg.CheckViolationError):
                await admin.execute("UPDATE public.supplier_funding_authorities SET cost_bearer='UNKNOWN' WHERE funding_authority_id=$1", authority_id)
            with self.assertRaises(asyncpg.CheckViolationError):
                await admin.execute("UPDATE public.route_decisions SET funding_authority_id=NULL,funding_authority_version=NULL,funding_authority_digest=NULL WHERE task_id=$1", task_id)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("UPDATE public.supplier_funding_authorities SET cost_bearer='JOUS_BORNE' WHERE funding_authority_id=$1", authority_id)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await runtime.execute("UPDATE public.supplier_funding_authorities SET funding_authority_id=$1 WHERE funding_authority_id=$2", uuid4(), authority_id)
            execution_id = uuid4()
            usage = {"input_tokens":11,"output_tokens":7,"total_tokens":18}
            await admin.execute("""INSERT INTO public.executions
              (id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,status,
               response_text,reported_provider_id,usage,usage_status,request_started_at,response_received_at,
               credential_authority_ref)
              VALUES($1,$2,$3,$4,$5,$6,'succeeded','ok','provider-a',$7::jsonb,'available',$8,$8,
               'fixture:jous-account')""",
              execution_id, task_id, org_id, project_id, user_id, task.dispatch_claim_id,
              json.dumps(usage), now)
            with self.assertRaises(asyncpg.CheckViolationError):
                await admin.execute("""INSERT INTO public.executions
                  (id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,status,
                   response_text,reported_provider_id,usage,usage_status,request_started_at,response_received_at,
                   credential_authority_ref)
                  VALUES($1,$2,$3,$4,$5,$6,'succeeded','ok','provider-a',$7::jsonb,'available',$8,$8,
                   'fixture:wrong-account')""", uuid4(), task_id, org_id, project_id, user_id,
                  task.dispatch_claim_id, json.dumps(usage), now)
            with self.assertRaises(asyncpg.CheckViolationError):
                await admin.execute("UPDATE public.executions SET credential_authority_ref='fixture:wrong-account' WHERE id=$1",
                                    execution_id)
            execution = SimpleNamespace(id=execution_id, task_id=task_id, organization_id=org_id,
                project_id=project_id, actor_user_id=user_id, dispatch_claim_id=task.dispatch_claim_id,
                usage_status="available", usage=usage, reported_provider_id="provider-a",
                response_received_at=now, request_started_at=now, recorded_at=now,
                credential_authority_ref="fixture:jous-account")
            decision = SimpleNamespace(task_id=task_id, dispatch_claim_id=task.dispatch_claim_id,
                organization_id=org_id, project_id=project_id, actor_user_id=user_id,
                logical_model_id="jous.text.general.v1", logical_model_version=1,
                selected_route_id="route-bind", selected_route_version=1, pricing_version_id=price_id)
            dispatch_route = SimpleNamespace(route_id="route-bind", supplier_id="local",
                underlying_provider="provider-a")
            event = normalize_execution(task, execution, route_decision=decision,
                                        dispatch_route=dispatch_route)
            event_columns = ["usage_event_id","organization_id","project_id","actor_user_id","task_id",
                "dispatch_claim_id","execution_id","route_decision_id","logical_model_id","logical_model_version",
                "route_id","route_version","supplier_id","underlying_provider","reported_provider_id",
                "input_tokens","output_tokens","total_tokens","cached_input_tokens","reasoning_tokens",
                "usage_status","source_type","source_reference","source_revision","observed_at",
                "normalizer_version","canonical_payload","evidence_sha256","supersedes_usage_event_id"]
            await admin.execute("INSERT INTO public.usage_events ("+",".join(event_columns)+") VALUES ("+
                ",".join(f"${i}" for i in range(1,len(event_columns)+1))+")",
                *[getattr(event, name) for name in event_columns])

            async def create_authority(*, authority_scope, authority_org, owner, bearer, evidence_ref,
                                       route_id="route-bind"):
                authority_id_value = uuid4()
                digest_value = await admin.fetchval("""WITH e AS (SELECT pg_catalog.jsonb_build_object(
                  'schema_version','jous.supplier-funding-authority.v1','funding_authority_id',$1::uuid,
                  'authority_version',1,'scope',$2::text,'organization_id',$3::uuid,'supplier_id','local',
                  'route_id',$8::text,'route_version',1,'credential_authority_ref','fixture:opaque-account',
                  'account_owner',$4::text,'cost_bearer',$5::text,'evidence_type','controlled_fixture',
                  'evidence_reference',$6::text,'effective_at',pg_catalog.to_char(
                    $7::timestamptz AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))::text AS canonical)
                  INSERT INTO public.supplier_funding_authorities
                  (funding_authority_id,authority_version,scope,organization_id,supplier_id,route_id,route_version,
                   credential_authority_ref,account_owner,cost_bearer,evidence_type,evidence_reference,effective_at,
                   canonical_evidence,authority_digest)
                  SELECT $1,1,$2,$3,'local',$8,1,'fixture:opaque-account',$4,$5,
                    'controlled_fixture',$6,$7,e.canonical,
                    pg_catalog.sha256(pg_catalog.convert_to(e.canonical,'UTF8')) FROM e RETURNING authority_digest""",
                    authority_id_value, authority_scope, authority_org, owner, bearer, evidence_ref, now, route_id)
                return authority_id_value, digest_value

            async def create_source_event(*, source_user, source_org, source_project, authority_binding=None,
                                          legacy=False, route_id="route-bind", bound_price_id=None):
                selected_price_id = price_id if bound_price_id is None else bound_price_id
                source_task_id = await create_task(admin, source_user, source_org, source_project, uuid4())
                source_task_values = dict(await admin.fetchrow("SELECT * FROM public.tasks WHERE id=$1", source_task_id))
                if isinstance(source_task_values["request_parameters"], str):
                    source_task_values["request_parameters"] = json.loads(source_task_values["request_parameters"])
                source_task = SimpleNamespace(**source_task_values)
                if not legacy:
                    source_snapshot = {"decision_version":"route-decision.v1","logical_model_id":"jous.text.general.v1",
                        "logical_model_version":1,"selector_version":"economic.v0","decision_time":now.isoformat(),
                        "input_token_bound":1,"output_allowance":1024,"selected":{"route_id":route_id,
                        "route_version":1,"pricing_version_id":selected_price_id,"estimated_cost":"0.123","currency":"USD"},
                        "candidate_evaluations":[{"route_id":route_id}]}
                    source_snapshot_text = exact_snapshot_bytes(source_snapshot)
                    columns = INSERT_DECISION.replace(
                        "decision_snapshot,snapshot_sha256)",
                        "decision_snapshot,snapshot_sha256,funding_authority_id,funding_authority_version,funding_authority_digest)")
                    columns = columns.replace("$9,$10)", "$9,$10,$11,$12,$13)")
                    columns = columns.replace("'route-bind',1,'standard'", f"'{route_id}',1,'standard'")
                    authority_values = (None, None, None) if authority_binding is None else (
                        authority_binding[0], 1, authority_binding[1])
                    await admin.execute(columns, source_task_id, source_org, source_project, source_user,
                        source_task.dispatch_claim_id, now, selected_price_id, BILLING_BASIS, source_snapshot_text,
                        hashlib.sha256(source_snapshot_text.encode()).digest(), *authority_values)
                source_execution_id = uuid4()
                source_usage = {"input_tokens":11,"output_tokens":7,"total_tokens":18}
                credential_ref = None
                if authority_binding is not None:
                    credential_ref = await admin.fetchval("""SELECT credential_authority_ref
                      FROM public.supplier_funding_authorities WHERE funding_authority_id=$1 AND authority_version=1""",
                      authority_binding[0])
                await admin.execute("""INSERT INTO public.executions
                  (id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,status,
                   response_text,reported_provider_id,usage,usage_status,request_started_at,response_received_at,
                   credential_authority_ref)
                  VALUES($1,$2,$3,$4,$5,$6,'succeeded','ok','provider-a',$7::jsonb,'available',$8,$8,$9)""",
                  source_execution_id, source_task_id, source_org, source_project, source_user,
                  source_task.dispatch_claim_id, json.dumps(source_usage), now, credential_ref)
                source_execution = SimpleNamespace(id=source_execution_id, task_id=source_task_id,
                    organization_id=source_org, project_id=source_project, actor_user_id=source_user,
                    dispatch_claim_id=source_task.dispatch_claim_id, usage_status="available", usage=source_usage,
                    reported_provider_id="provider-a", response_received_at=now, request_started_at=now,
                    recorded_at=now, credential_authority_ref=credential_ref)
                source_decision = None if legacy else SimpleNamespace(task_id=source_task_id,
                    dispatch_claim_id=source_task.dispatch_claim_id, organization_id=source_org,
                    project_id=source_project, actor_user_id=source_user, logical_model_id="jous.text.general.v1",
                    logical_model_version=1, selected_route_id=route_id, selected_route_version=1,
                    pricing_version_id=selected_price_id)
                source_route = None if source_decision is None else SimpleNamespace(route_id=route_id,
                    supplier_id="local", underlying_provider="provider-a")
                source_event = normalize_execution(source_task, source_execution, route_decision=source_decision,
                                                   dispatch_route=source_route)
                await admin.execute("INSERT INTO public.usage_events ("+",".join(event_columns)+") VALUES ("+
                    ",".join(f"${i}" for i in range(1,len(event_columns)+1))+")",
                    *[getattr(source_event, name) for name in event_columns])
                return source_event

            gateway_price_id = "v14c-gateway-" + uuid4().hex
            await admin.execute("""INSERT INTO public.route_pricing_versions
              (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,
               input_price_per_1m,output_price_per_1m,provider_fee_applicable,provider_request_fee_usd,
               gateway_fee_applicable,gateway_request_fee_usd,fee_basis_verified,source_type,
               source_evidence_id,reviewed_at,effective_from,valid_until,pricing_status)
              VALUES($1,'route-gateway',1,'standard','USD',$2,1,1,false,NULL,true,0.000000000001,true,
                'manual_review','gateway-evidence',$3::timestamptz,$3::timestamptz+interval '2 hours',
                $3::timestamptz+interval '3 hours','approved')""", gateway_price_id, BILLING_BASIS, now)
            gateway_authority = await create_authority(authority_scope="JOUS_GLOBAL", authority_org=None,
                owner="JOUS", bearer="JOUS_BORNE", evidence_ref="fixture:gateway-account", route_id="route-gateway")
            gateway_event = await create_source_event(source_user=user_id, source_org=org_id,
                source_project=project_id, authority_binding=gateway_authority, route_id="route-gateway",
                bound_price_id=gateway_price_id)

            customer_user, customer_org, customer_project = uuid4(), uuid4(), uuid4()
            await admin.execute("INSERT INTO public.users(id) VALUES($1)", customer_user)
            await admin.execute("INSERT INTO public.organizations(id,name) VALUES($1,'economic-customer-test')", customer_org)
            await admin.execute("INSERT INTO public.organization_memberships(id,user_id,organization_id,role) VALUES($1,$2,$3,'owner')",
                                uuid4(), customer_user, customer_org)
            await admin.execute("INSERT INTO public.projects(id,organization_id,name) VALUES($1,$2,'economic-customer-test')",
                                customer_project, customer_org)
            customer_authority = await create_authority(authority_scope="ORGANIZATION", authority_org=customer_org,
                owner="CUSTOMER", bearer="CUSTOMER_DIRECT", evidence_ref="fixture:customer-direct")
            with self.assertRaises(asyncpg.CheckViolationError):
                await create_source_event(source_user=user_id, source_org=org_id, source_project=project_id,
                                          authority_binding=customer_authority)
            customer_event = await create_source_event(source_user=customer_user, source_org=customer_org,
                source_project=customer_project, authority_binding=customer_authority)
            unknown_event = await create_source_event(source_user=user_id, source_org=org_id,
                source_project=project_id, legacy=True)
            token_evidence = await processor.fetchrow("""SELECT usage_event_id,organization_id,project_id,
              actor_user_id,task_id,dispatch_claim_id,execution_id,route_decision_id,usage_status,
              evidence_sha256,observed_at,supplier_id,input_tokens,output_tokens FROM public.usage_events
              WHERE usage_event_id=$1""", event.usage_event_id)
            self.assertEqual((token_evidence["input_tokens"], token_evidence["output_tokens"]), (11, 7))
            self.assertEqual(token_evidence["supplier_id"], "local")
            self.assertEqual((token_evidence["usage_event_id"], token_evidence["evidence_sha256"]),
                             (event.usage_event_id, event.evidence_sha256))
            # Production receipt derivation accepts only the immutable event ID.
            from sqlalchemy.engine import make_url
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from jous_api.economic_receipts import (
                CALCULATION_VERSION, ECONOMIC_POLICY_VERSION, TREATMENT_POLICY_DIGEST,
                derive_and_persist_economic_receipt,
            )
            from jous_api.economic_ledger_posting import post_economic_receipt
            receipt_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            try:
                ledger_before = (await processor.fetchval("SELECT count(*) FROM public.ledger_transactions"),
                                 await processor.fetchval("SELECT count(*) FROM public.ledger_entries"))
                async with AsyncSession(receipt_engine) as receipt_session:
                    derived = await derive_and_persist_economic_receipt(receipt_session, event.usage_event_id)
                    replayed = await derive_and_persist_economic_receipt(receipt_session, event.usage_event_id)
                    customer_derived = await derive_and_persist_economic_receipt(receipt_session, customer_event.usage_event_id)
                    customer_replayed = await derive_and_persist_economic_receipt(receipt_session, customer_event.usage_event_id)
                    unknown_derived = await derive_and_persist_economic_receipt(receipt_session, unknown_event.usage_event_id)
                    unknown_replayed = await derive_and_persist_economic_receipt(receipt_session, unknown_event.usage_event_id)
                    gateway_derived = await derive_and_persist_economic_receipt(receipt_session, gateway_event.usage_event_id)
                self.assertEqual(derived["economic_receipt_id"], replayed["economic_receipt_id"])
                self.assertEqual(derived["assessment_key"], replayed["assessment_key"])
                self.assertEqual(derived["canonical_digest"], replayed["canonical_digest"])
                self.assertIsNone(derived["supersedes_receipt_id"])
                self.assertEqual(derived["cost_bearer"], "JOUS_BORNE")
                self.assertEqual(derived["funding_authority_id"], authority_id)
                self.assertEqual(derived["funding_authority_version"], 1)
                self.assertEqual(derived["funding_authority_digest"], authority_digest)
                self.assertEqual(customer_derived["cost_bearer"], "CUSTOMER_DIRECT")
                self.assertEqual(customer_derived["organization_id"], customer_org)
                self.assertEqual(customer_derived["funding_authority_id"], customer_authority[0])
                self.assertEqual(customer_derived["funding_authority_digest"], customer_authority[1])
                self.assertEqual(customer_derived["economic_receipt_id"], customer_replayed["economic_receipt_id"])
                self.assertEqual(customer_derived["canonical_digest"], customer_replayed["canonical_digest"])
                self.assertEqual(unknown_derived["cost_bearer"], "UNKNOWN")
                self.assertIsNone(unknown_derived["funding_authority_id"])
                self.assertEqual(unknown_derived["assessment_status"], "MISSING_PRICING")
                self.assertIsNone(unknown_derived["computed_usage_cost_usd"])
                self.assertEqual(unknown_derived["economic_receipt_id"], unknown_replayed["economic_receipt_id"])
                self.assertEqual(unknown_derived["canonical_digest"], unknown_replayed["canonical_digest"])
                self.assertEqual(derived["assessment_status"], "COMPUTED")
                self.assertEqual(gateway_derived["provider_usage_cost_usd"], __import__('decimal').Decimal("0.000018000000000000"))
                self.assertEqual(gateway_derived["gateway_request_fee_usd"], __import__('decimal').Decimal("0.000000000001000000"))
                self.assertEqual(gateway_derived["computed_usage_cost_usd"], __import__('decimal').Decimal("0.000018000001000000"))
                self.assertEqual(derived["organization_id"], event.organization_id)
                self.assertEqual(derived["project_id"], event.project_id)
                self.assertEqual(derived["actor_user_id"], event.actor_user_id)
                self.assertEqual(derived["task_id"], event.task_id)
                self.assertEqual(derived["dispatch_claim_id"], event.dispatch_claim_id)
                self.assertEqual(derived["execution_id"], event.execution_id)
                self.assertEqual(derived["usage_event_id"], event.usage_event_id)
                self.assertEqual(derived["route_decision_id"], event.route_decision_id)
                self.assertEqual(derived["pricing_version_id"], price_id)
                self.assertEqual(derived["source_usage_digest"], event.evidence_sha256)
                expected_assessment_key = await processor.fetchval("""SELECT pg_catalog.sha256(
                  pg_catalog.convert_to(pg_catalog.jsonb_build_object(
                    'schema_version','jous.economic-assessment.v1','usage_event_id',$1::uuid,
                    'economic_policy_version',$2::text,'treatment_policy_digest',
                    pg_catalog.encode($3::bytea,'hex'),'calculation_version',$4::text,
                    'pricing_version_id',$5::varchar,'funding_authority_digest',
                    pg_catalog.encode($6::bytea,'hex'))::text,'UTF8'))""",
                    event.usage_event_id, ECONOMIC_POLICY_VERSION, TREATMENT_POLICY_DIGEST,
                    CALCULATION_VERSION, price_id, authority_digest)
                self.assertEqual(derived["assessment_key"], expected_assessment_key)
                expected_receipt_digest = await processor.fetchval("""SELECT pg_catalog.sha256(
                  pg_catalog.convert_to(pg_catalog.jsonb_build_object(
                    'schema_version','jous.economic-receipt.v1','economic_receipt_id',r.economic_receipt_id,
                    'assessment_key',pg_catalog.encode(r.assessment_key,'hex'),'organization_id',r.organization_id,
                    'project_id',r.project_id,'actor_user_id',r.actor_user_id,'task_id',r.task_id,
                    'dispatch_claim_id',r.dispatch_claim_id,'execution_id',r.execution_id,
                    'usage_event_id',r.usage_event_id,'route_decision_id',r.route_decision_id,
                    'pricing_version_id',r.pricing_version_id,'funding_authority_id',r.funding_authority_id,
                    'funding_authority_version',r.funding_authority_version,
                    'funding_authority_digest',pg_catalog.encode(r.funding_authority_digest,'hex'),
                    'economic_policy_version',r.economic_policy_version,
                    'treatment_policy_digest',pg_catalog.encode(r.treatment_policy_digest,'hex'),
                    'calculation_version',r.calculation_version,'assessment_status',r.assessment_status,
                    'cost_bearer',r.cost_bearer,'currency',r.currency,
                    'provider_usage_cost_usd',r.provider_usage_cost_usd,
                    'provider_request_fee_usd',r.provider_request_fee_usd,
                    'gateway_request_fee_usd',r.gateway_request_fee_usd,
                    'computed_usage_cost_usd',r.computed_usage_cost_usd,
                    'pricing_snapshot_sha256',CASE WHEN r.pricing_snapshot_sha256 IS NULL THEN NULL
                      ELSE pg_catalog.encode(r.pricing_snapshot_sha256,'hex') END,
                    'source_usage_digest',pg_catalog.encode(r.source_usage_digest,'hex'),
                    'supersedes_receipt_id',r.supersedes_receipt_id,
                    'observed_at',pg_catalog.to_char(r.observed_at AT TIME ZONE 'UTC',
                      'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))::text,'UTF8'))
                  FROM public.economic_receipts r WHERE r.economic_receipt_id=$1""",
                  derived["economic_receipt_id"])
                self.assertEqual(derived["canonical_digest"], expected_receipt_digest)
                self.assertEqual(derived["provider_usage_cost_usd"], __import__('decimal').Decimal("0.000018000000000000"))
                self.assertEqual(derived["provider_request_fee_usd"], __import__('decimal').Decimal("0E-18"))
                self.assertEqual(derived["gateway_request_fee_usd"], __import__('decimal').Decimal("0E-18"))
                self.assertEqual(derived["computed_usage_cost_usd"], __import__('decimal').Decimal("0.000018000000000000"))
                parity_vectors = (
                    (11, 0, "1.000000000000", "0.000000000000"),
                    (0, 7, "0.000000000000", "2.000000000000"),
                    (11, 7, "1.000000000000", "2.000000000000"),
                    (0, 0, "0.000000000000", "0.000000000000"),
                    (11, 0, "0.000000000001", "0.000000000000"),
                    (2**63-1, 2**63-1, "99999999.999999999999", "99999999.999999999999"),
                )
                for in_tokens, out_tokens, in_rate, out_rate in parity_vectors:
                    pg_amount = await processor.fetchval("""SELECT
                      ($1::bigint::numeric*$3::numeric+$2::bigint::numeric*$4::numeric)*0.000001::numeric""",
                      in_tokens,out_tokens,in_rate,out_rate)
                    with __import__('decimal').localcontext() as ctx:
                        ctx.prec = 100
                        py_amount = (__import__('decimal').Decimal(in_tokens)*__import__('decimal').Decimal(in_rate)
                                     + __import__('decimal').Decimal(out_tokens)*__import__('decimal').Decimal(out_rate)) \
                                    / __import__('decimal').Decimal(1_000_000)
                    self.assertEqual(pg_amount, py_amount)
                self.assertEqual(hashlib.sha256(derived["pricing_snapshot_canonical"].encode("utf-8")).digest(),
                                 derived["pricing_snapshot_sha256"])
                pricing_payload = json.loads(derived["pricing_snapshot_canonical"])
                self.assertEqual(pricing_payload["pricing_version_id"], price_id)
                self.assertEqual(pricing_payload["input_price_per_1m"], "1.000000000000")
                self.assertEqual(pricing_payload["output_price_per_1m"], "1.000000000000")
                self.assertEqual(await processor.fetchval(
                    "SELECT count(*) FROM public.economic_receipts WHERE usage_event_id=$1", event.usage_event_id), 1)
                self.assertEqual((await processor.fetchval("SELECT count(*) FROM public.ledger_transactions"),
                                  await processor.fetchval("SELECT count(*) FROM public.ledger_entries")), ledger_before)
                # Production service posts only from a persisted receipt ID and
                # resolves journal components/accounts from immutable rows.
                first_post = await post_economic_receipt(receipt_session, derived["economic_receipt_id"])
                replay_post = await post_economic_receipt(receipt_session, derived["economic_receipt_id"])
                self.assertEqual(first_post.status, "POSTED")
                self.assertTrue(first_post.created)
                self.assertEqual(first_post.entry_count, 2)
                self.assertEqual(replay_post.status, "POSTED")
                self.assertFalse(replay_post.created)
                self.assertEqual(replay_post.ledger_transaction_id, first_post.ledger_transaction_id)
                for ineligible_receipt in (customer_derived, unknown_derived):
                    result = await post_economic_receipt(
                        receipt_session, ineligible_receipt["economic_receipt_id"])
                    self.assertEqual(result.status, "INELIGIBLE")
                posted_lines = await processor.fetch("""SELECT a.account_code,e.direction,e.amount
                  FROM public.ledger_entries e JOIN public.ledger_accounts a USING(ledger_account_id)
                  WHERE e.ledger_transaction_id=$1 ORDER BY e.line_number""",
                  first_post.ledger_transaction_id)
                self.assertEqual([(r["account_code"], r["direction"], r["amount"])
                                  for r in posted_lines], [
                    ("provider_inference_expense", "DEBIT", __import__('decimal').Decimal("0.000018000000000000")),
                    ("supplier_cost_accrual", "CREDIT", __import__('decimal').Decimal("0.000018000000000000")),
                ])
                self.assertEqual((await processor.fetchval("SELECT count(*) FROM public.ledger_transactions"),
                                  await processor.fetchval("SELECT count(*) FROM public.ledger_entries")),
                                 (ledger_before[0] + 1, ledger_before[1] + 2))
            finally:
                await receipt_engine.dispose()
            for forbidden in ("canonical_payload", "cached_input_tokens", "reported_provider_id"):
                with self.subTest(forbidden=forbidden), self.assertRaises(asyncpg.InsufficientPrivilegeError):
                    await processor.fetch(f"SELECT {forbidden} FROM public.usage_events WHERE usage_event_id=$1",
                                          event.usage_event_id)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("INSERT INTO public.usage_events(usage_event_id) VALUES($1)", uuid4())
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("UPDATE public.usage_events SET input_tokens=99 WHERE usage_event_id=$1",
                                        event.usage_event_id)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("DELETE FROM public.usage_events WHERE usage_event_id=$1",
                                        event.usage_event_id)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("TRUNCATE public.usage_events")
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                await processor.execute("CREATE TRIGGER v14c_acl_probe BEFORE INSERT ON public.usage_events "
                    "FOR EACH ROW EXECUTE FUNCTION public.validate_economic_receipt_source()")

            pricing_row = await processor.fetchrow("""SELECT pricing_version_id,route_id,route_version,
              service_tier,currency,billing_basis,input_price_per_1m,output_price_per_1m,
              provider_fee_applicable,provider_request_fee_usd,gateway_fee_applicable,
              gateway_request_fee_usd,fee_basis_verified,source_type,source_evidence_id,
              reviewed_at,effective_from,valid_until FROM public.route_pricing_versions
              WHERE pricing_version_id=$1""", price_id)
            pricing = {"schema_version":"jous.route-pricing.v1", **dict(pricing_row)}
            pricing = {k:(v.isoformat() if isinstance(v,datetime) else str(v) if k in
                {"input_price_per_1m","output_price_per_1m","provider_request_fee_usd","gateway_request_fee_usd"}
                and v is not None else v) for k,v in pricing.items()}
            pricing_text = json.dumps(pricing, sort_keys=True, separators=(",",":"))
            source_digest = event.evidence_sha256
            receipt_id = uuid4()
            async def receipt(bearer="JOUS_BORNE", amount="0.000018", digest=b"policy-one",
                              components=None, decision_id=None, price_id_override=None, supersedes=None,
                              conn=None):
                conn = processor if conn is None else conn
                components = components or (amount, "0", "0")
                amount = None if amount is None else amount
                decision_id = task_id if decision_id is None else decision_id
                bound_price_id = price_id if price_id_override is None else price_id_override
                computed = None if amount is None else str(sum((__import__('decimal').Decimal(v) for v in components), __import__('decimal').Decimal(0)))
                return await conn.fetchrow("""INSERT INTO public.economic_receipts
                  (economic_receipt_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,
                   execution_id,usage_event_id,route_decision_id,pricing_version_id,funding_authority_id,
                   funding_authority_version,funding_authority_digest,economic_policy_version,
                   treatment_policy_digest,calculation_version,assessment_status,cost_bearer,currency,
                   provider_usage_cost_usd,provider_request_fee_usd,gateway_request_fee_usd,
                   computed_usage_cost_usd,pricing_snapshot_canonical,pricing_snapshot_sha256,
                   source_usage_digest,observed_at,supersedes_receipt_id)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,1,$12,'policy.v1',$13,'calc.v1','COMPUTED',$14,
                   'USD',$15,$16,$17,$18,$19,$20,$21,$22,$23)
                  RETURNING economic_receipt_id,canonical_digest,assessment_key""",
                  uuid4(),org_id,project_id,user_id,task_id,task.dispatch_claim_id,execution_id,
                  event.usage_event_id,decision_id,bound_price_id,authority_id,authority_digest,
                  hashlib.sha256(digest).digest(),bearer,*components,computed,pricing_text,
                  hashlib.sha256(pricing_text.encode()).digest(),source_digest,now,supersedes)

            valid_receipt = await receipt()
            async def forged_amounts(provider, provider_fee, gateway_fee, total):
                return await processor.execute("""INSERT INTO public.economic_receipts
                  (economic_receipt_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,
                   execution_id,usage_event_id,route_decision_id,pricing_version_id,funding_authority_id,
                   funding_authority_version,funding_authority_digest,economic_policy_version,
                   treatment_policy_digest,calculation_version,assessment_status,cost_bearer,currency,
                   provider_usage_cost_usd,provider_request_fee_usd,gateway_request_fee_usd,
                   computed_usage_cost_usd,pricing_snapshot_canonical,pricing_snapshot_sha256,
                   source_usage_digest,observed_at)
                  SELECT gen_random_uuid(),organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,
                   execution_id,usage_event_id,route_decision_id,pricing_version_id,funding_authority_id,
                   funding_authority_version,funding_authority_digest,'attack.'||$5::text,treatment_policy_digest,
                   calculation_version,assessment_status,cost_bearer,currency,$1,$2,$3,$4,
                   pricing_snapshot_canonical,pricing_snapshot_sha256,source_usage_digest,observed_at
                  FROM public.economic_receipts WHERE economic_receipt_id=$6""",
                  provider, provider_fee, gateway_fee, total, uuid4().hex,
                  valid_receipt["economic_receipt_id"])

            canonical_provider = __import__('decimal').Decimal("0.000018")
            scale18 = __import__('decimal').Decimal("0.000000000000000001")
            for label, values in (
                ("inflated provider", (canonical_provider + scale18, 0, 0, canonical_provider + scale18)),
                ("reduced provider", (canonical_provider - scale18, 0, 0, canonical_provider - scale18)),
                ("fabricated gateway", (canonical_provider, 0, scale18, canonical_provider + scale18)),
                ("wrong total", (canonical_provider, 0, 0, canonical_provider + scale18)),
                ("component shift", (canonical_provider - scale18, 0, scale18, canonical_provider)),
            ):
                with self.subTest(calculation_attack=label), self.assertRaises(asyncpg.CheckViolationError):
                    await forged_amounts(*values)
            tx_id = uuid4()
            async with processor.transaction():
                await processor.execute("""INSERT INTO public.ledger_entries VALUES
                    ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000018),
                    ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000018)""",
                    tx_id, org_id)
                await processor.execute("""INSERT INTO public.ledger_transactions
                  (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                  VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                  tx_id, org_id, valid_receipt["economic_receipt_id"], valid_receipt["canonical_digest"])
            self.assertEqual(await processor.fetchval("SELECT count(*) FROM public.ledger_entries WHERE ledger_transaction_id=$1", tx_id), 2)
            with self.assertRaises(asyncpg.CheckViolationError):
                await processor.execute("""INSERT INTO public.ledger_entries VALUES
                  ($1,$2,3,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000001)""", tx_id, org_id)
            with self.assertRaises(asyncpg.UniqueViolationError):
                await processor.execute("""INSERT INTO public.ledger_transactions
                  (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                  VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                  uuid4(), org_id, valid_receipt["economic_receipt_id"], valid_receipt["canonical_digest"])

            # A persisted applicable gateway fee is independently validated and posted.
            posting_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            try:
                async with AsyncSession(posting_engine) as posting_session:
                    service_three_line = await post_economic_receipt(
                        posting_session, gateway_derived["economic_receipt_id"])
                self.assertEqual(service_three_line.status, "POSTED")
                self.assertTrue(service_three_line.created)
                self.assertEqual(service_three_line.entry_count, 3)
                service_lines = await processor.fetch("""SELECT a.account_code,e.direction,e.amount
                  FROM public.ledger_entries e JOIN public.ledger_accounts a USING(ledger_account_id)
                  WHERE e.ledger_transaction_id=$1 ORDER BY e.line_number""",
                  service_three_line.ledger_transaction_id)
                self.assertEqual([(r["account_code"],r["direction"],r["amount"])
                                  for r in service_lines], [
                    ("provider_inference_expense", "DEBIT", __import__('decimal').Decimal("0.000018000000000000")),
                    ("gateway_platform_expense", "DEBIT", __import__('decimal').Decimal("0.000000000001000000")),
                    ("supplier_cost_accrual", "CREDIT", __import__('decimal').Decimal("0.000018000001000000")),
                ])
            finally:
                await posting_engine.dispose()
            concurrent_receipt = await receipt(digest=b"concurrent-production-posting")
            concurrency_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            try:
                async def post_once():
                    async with AsyncSession(concurrency_engine) as posting_session:
                        return await post_economic_receipt(
                            posting_session, concurrent_receipt["economic_receipt_id"])
                concurrent_results = await asyncio.gather(post_once(), post_once())
                self.assertEqual([r.status for r in concurrent_results], ["POSTED", "POSTED"])
                self.assertEqual(sum(r.created for r in concurrent_results), 1)
                self.assertEqual(len({r.ledger_transaction_id for r in concurrent_results}), 1)
                self.assertEqual(await processor.fetchval(
                    "SELECT count(*) FROM public.ledger_transactions WHERE economic_receipt_id=$1",
                    concurrent_receipt["economic_receipt_id"]), 1)
            finally:
                await concurrency_engine.dispose()
            three_line_receipt = await receipt(digest=b"policy-three-line")
            three_line_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                        ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000017),
                        ($1,$2,2,'b4000000-0000-4000-8000-000000000002','USD','DEBIT',0.000001),
                        ($1,$2,3,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000018)""",
                        three_line_tx,org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      three_line_tx,org_id,three_line_receipt["economic_receipt_id"],three_line_receipt["canonical_digest"])

            mismatched_receipt = await receipt(digest=b"policy-mismatch")
            mismatched_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000002),
                      ($1,$2,2,'b4000000-0000-4000-8000-000000000002','USD','DEBIT',0.000000000000000002),
                      ($1,$2,3,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000004)""",
                      mismatched_tx,org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      mismatched_tx,org_id,mismatched_receipt["economic_receipt_id"],mismatched_receipt["canonical_digest"])

            # A second receipt cannot mint an arbitrary balanced journal for unrelated classifications.
            bad_receipt = await receipt(digest=b"policy-two")
            bad_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000002','USD','DEBIT',0.000000000000000001),
                      ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000001)""", bad_tx, org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      bad_tx, org_id, bad_receipt["economic_receipt_id"], bad_receipt["canonical_digest"])

            # The deferred constraint also rejects empty, single-line and orphan journals.
            empty_receipt = await receipt(digest=b"policy-empty")
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      uuid4(), org_id, empty_receipt["economic_receipt_id"], empty_receipt["canonical_digest"])
            with self.assertRaises(asyncpg.ForeignKeyViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000001),
                      ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000001)""",
                      uuid4(), org_id)
            one_line_receipt = await receipt(digest=b"policy-one-line")
            one_line_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000001)""",
                      one_line_tx, org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      one_line_tx, org_id, one_line_receipt["economic_receipt_id"], one_line_receipt["canonical_digest"])
            unbalanced_receipt = await receipt(digest=b"policy-unbalanced")
            unbalanced_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000002),
                      ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000001)""",
                      unbalanced_tx, org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      unbalanced_tx, org_id, unbalanced_receipt["economic_receipt_id"], unbalanced_receipt["canonical_digest"])
            with self.assertRaises(asyncpg.CheckViolationError):
                await processor.execute("""INSERT INTO public.ledger_entries VALUES
                  ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0)""", uuid4(), org_id)
            with self.assertRaises((asyncpg.CheckViolationError, asyncpg.InsufficientPrivilegeError)):
                await processor.execute("""INSERT INTO public.ledger_entries VALUES
                  ($1,$2,1,'b4000000-0000-4000-8000-000000000001','EUR','DEBIT',1)""", uuid4(), org_id)
            with self.assertRaises(asyncpg.CheckViolationError):
                await processor.execute("""INSERT INTO public.ledger_entries VALUES
                  ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',-1)""", uuid4(), org_id)

            # Unknown/customer-direct and known-zero receipts cannot create postings.
            for candidate in (unknown_derived, customer_derived):
                with self.assertRaises(asyncpg.CheckViolationError):
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      uuid4(), candidate["organization_id"], candidate["economic_receipt_id"], candidate["canonical_digest"])
            with self.assertRaises(asyncpg.CheckViolationError):
                await receipt(amount="0", digest=b"policy-zero")
            from sqlalchemy.engine import make_url
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            posting_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            with self.assertRaises(asyncpg.UniqueViolationError):
                await receipt(digest=b"policy-one")
            predecessor = await receipt(digest=b"supersession-predecessor")
            successor = await receipt(digest=b"supersession-successor",
                                      supersedes=predecessor["economic_receipt_id"])
            self.assertIsNotNone(successor)
            # Direct processor SQL must be stopped by the database, independently
            # of the Python posting service.
            pre_repair_tx = uuid4()
            with self.assertRaises(asyncpg.CheckViolationError):
                async with processor.transaction():
                    await processor.execute("""INSERT INTO public.ledger_entries VALUES
                        ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000001),
                        ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000001)""",
                        pre_repair_tx, org_id)
                    await processor.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      pre_repair_tx, org_id, predecessor["economic_receipt_id"], predecessor["canonical_digest"])
            self.assertEqual(await processor.fetchval(
                "SELECT count(*) FROM public.ledger_transactions WHERE ledger_transaction_id=$1", pre_repair_tx), 0)
            posting_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            try:
                async with AsyncSession(posting_engine) as posting_session:
                    predecessor_result = await post_economic_receipt(
                        posting_session, predecessor["economic_receipt_id"])
                    successor_result = await post_economic_receipt(
                        posting_session, successor["economic_receipt_id"])
                self.assertEqual(predecessor_result.reason, "RECEIPT_SUPERSEDED")
                self.assertEqual(successor_result.reason, "RECEIPT_IS_SUPERSESSION")
            finally:
                await posting_engine.dispose()

            # A successor arriving after a committed posting does not rewrite,
            # delete, or duplicate that historical immutable journal.
            historical_receipt = await receipt(digest=b"posted-before-supersession")
            history_engine = create_async_engine(make_url(self.processor_url).set(
                drivername="postgresql+asyncpg"), echo=False, hide_parameters=True)
            try:
                async with AsyncSession(history_engine) as posting_session:
                    historical_post = await post_economic_receipt(
                        posting_session, historical_receipt["economic_receipt_id"])
                self.assertEqual(historical_post.status, "POSTED")
                before_history = await processor.fetchrow("""SELECT count(*) AS n,
                  sum(amount) AS amount FROM public.ledger_entries WHERE ledger_transaction_id=$1""",
                  historical_post.ledger_transaction_id)
                await receipt(digest=b"successor-after-posting",
                              supersedes=historical_receipt["economic_receipt_id"])
                async with AsyncSession(history_engine) as posting_session:
                    historical_replay = await post_economic_receipt(
                        posting_session, historical_receipt["economic_receipt_id"])
                after_history = await processor.fetchrow("""SELECT count(*) AS n,
                  sum(amount) AS amount FROM public.ledger_entries WHERE ledger_transaction_id=$1""",
                  historical_post.ledger_transaction_id)
                self.assertEqual(historical_replay.ledger_transaction_id,
                                 historical_post.ledger_transaction_id)
                self.assertEqual(tuple(after_history), tuple(before_history))
            finally:
                await history_engine.dispose()

            # Successor insertion and posting share a receipt-scoped advisory
            # transaction lock. Successor wins here, so a posting already
            # waiting on that identity must fail and roll back all entry rows.
            race_receipt = await receipt(digest=b"supersession-race")
            successor_conn = await asyncpg.connect(self.processor_url)
            poster_conn = await asyncpg.connect(self.processor_url)
            successor_tx = successor_conn.transaction()
            await successor_tx.start()
            race_successor = await receipt(
                digest=b"supersession-race-successor",
                supersedes=race_receipt["economic_receipt_id"], conn=successor_conn)
            self.assertIsNotNone(race_successor)
            race_post_tx_id = uuid4()
            poster_pid = await poster_conn.fetchval("SELECT pg_backend_pid()")
            async def race_post_attempt():
                async with poster_conn.transaction():
                    await poster_conn.execute("""INSERT INTO public.ledger_entries VALUES
                      ($1,$2,1,'b4000000-0000-4000-8000-000000000001','USD','DEBIT',0.000000000000000001),
                      ($1,$2,2,'b4000000-0000-4000-8000-000000000003','USD','CREDIT',0.000000000000000001)""",
                      race_post_tx_id, org_id)
                    await poster_conn.execute("""INSERT INTO public.ledger_transactions
                      (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest)
                      VALUES($1,$2,$3,'COMPUTED_JOUS_COST_V1','USD',$4)""",
                      race_post_tx_id, org_id, race_receipt["economic_receipt_id"],
                      race_receipt["canonical_digest"])
            race_task = asyncio.create_task(race_post_attempt())
            try:
                deadline = asyncio.get_running_loop().time() + 5
                waiting_on_advisory = False
                while asyncio.get_running_loop().time() < deadline:
                    wait_state = await admin.fetchrow("""SELECT wait_event_type,wait_event
                      FROM pg_catalog.pg_stat_activity WHERE pid=$1""", poster_pid)
                    if wait_state and wait_state["wait_event_type"] == "Lock" and \
                            wait_state["wait_event"] == "advisory":
                        waiting_on_advisory = True
                        break
                    if race_task.done():
                        race_task.result()
                        break
                    await asyncio.sleep(0.02)
                self.assertTrue(waiting_on_advisory,
                                "posting did not serialize behind successor insertion")
                await successor_tx.commit()
                with self.assertRaises(asyncpg.CheckViolationError):
                    await race_task
                self.assertEqual(await admin.fetchval(
                    "SELECT count(*) FROM public.ledger_transactions WHERE ledger_transaction_id=$1",
                    race_post_tx_id), 0)
                self.assertEqual(await admin.fetchval(
                    "SELECT count(*) FROM public.ledger_entries WHERE ledger_transaction_id=$1",
                    race_post_tx_id), 0)
            finally:
                try:
                    await successor_tx.rollback()
                except (asyncpg.InterfaceError, asyncpg.PostgresError):
                    pass
                await successor_conn.close()
                await poster_conn.close()
            with self.assertRaises(asyncpg.UniqueViolationError):
                await receipt(digest=b"supersession-competing",
                              supersedes=predecessor["economic_receipt_id"])
            with self.assertRaises(asyncpg.ForeignKeyViolationError):
                await receipt(digest=b"route-mismatch", decision_id=uuid4())
            with self.assertRaises(asyncpg.CheckViolationError):
                await receipt(digest=b"pricing-mismatch", price_id_override="no-such-pricing-version")

            # Database must derive identity from the UsageEvent; caller cannot substitute tenant/project.
            with self.assertRaises(asyncpg.ForeignKeyViolationError):
                await processor.execute("""INSERT INTO public.economic_receipts
                  (economic_receipt_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,
                   execution_id,usage_event_id,economic_policy_version,treatment_policy_digest,
                   calculation_version,assessment_status,cost_bearer,currency,source_usage_digest,observed_at)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,'policy.v1',$9,'calc.v1','MISSING_PRICING','UNKNOWN','USD',$10,$11)""",
                  uuid4(),uuid4(),project_id,user_id,task_id,task.dispatch_claim_id,execution_id,
                  event.usage_event_id,hashlib.sha256(b"forged").digest(),source_digest,now)
        finally:
            await processor.close()
            await runtime.close()
            await admin.close()
