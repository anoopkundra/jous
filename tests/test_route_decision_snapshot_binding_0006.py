"""Explicitly gated behavior and transactional-upgrade test for fresh local PG17."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from uuid import uuid4
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get("JOUS_V13A_0006_DISPOSABLE_AUTHORIZED") == "YES"
FIELDS = (
    "decision_version", "logical_model_id", "logical_model_version", "selector_version",
    "decision_time", "input_token_bound", "output_allowance", "selected.route_id",
    "selected.route_version", "selected.pricing_version_id", "selected.estimated_cost",
    "selected.currency",
)
BILLING_BASIS = "input_output_tokens_plus_request_fees_v1"
INSERT_DECISION = """INSERT INTO public.route_decisions
 (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,decision_version,
  selector_version,logical_model_id,logical_model_version,decided_at,pricing_version_id,
  selected_route_id,selected_route_version,service_tier,currency,billing_basis,
  input_token_bound,output_allowance,estimated_cost_usd,decision_snapshot,snapshot_sha256)
 VALUES ($1,$2,$3,$4,$5,'route-decision.v1','economic.v0','jous.text.general.v1',1,
  $6,$7,'route-bind',1,'standard','USD',$8,1,1024,0.123,$9,$10)"""


def disposable_url():
    if not ENABLED:
        raise RuntimeError("Explicit fresh disposable PostgreSQL authorization required")
    value = os.environ.get("JOUS_V13A_0006_DISPOSABLE_ADMIN_URL", "")
    parsed = urlsplit(value)
    if (parsed.scheme != "postgresql" or parsed.hostname != "127.0.0.1"
            or parsed.username != "postgres" or not parsed.path.startswith("/jous_v13a_0006_")
            or parsed.query or parsed.fragment or not parsed.port):
        raise RuntimeError("Only the named loopback disposable PostgreSQL target is accepted")
    return value


def mutate_path(snapshot, path, *, remove=False, value=None):
    parts = path.split(".")
    target = snapshot
    for part in parts[:-1]:
        target = target[part]
    if remove:
        del target[parts[-1]]
    else:
        target[parts[-1]] = value


def exact_snapshot_bytes(snapshot):
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"))


async def create_task(connection, user_id, organization_id, project_id, claim_id):
    now = datetime.now(timezone.utc)
    task_id = uuid4()
    context_package = {"schema_version": 1, "snapshot": {}, "instruction": {}, "provenance": {}}
    request_parameters = {"schema_version": 1, "route_id": "route-bind", "catalog_digest": "x",
                          "route_snapshot": {}, "limits": {}, "execution": {}}
    token_evidence = {"schema_version": 1, "asset_revision": "local", "asset_hashes": {},
                      "method": "LOCAL_PROVISIONAL", "template_branch": "non-thinking",
                      "input_token_upper_bound": 1, "context_capacity": 32768,
                      "output_allowance": 1024, "safety_margin": 3277,
                      "hosted_authority_state": "HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED"}
    await connection.execute("""INSERT INTO public.tasks
      (id,organization_id,project_id,actor_user_id,client_request_id,request_sha256,prompt,
       context_package,context_sha256,logical_model_id,supplier_id,supplier_native_model_id,
       underlying_provider,admission_version,request_parameters,tokenizer_manifest_sha256,
       template_branch,token_bound_method,token_bound_evidence,input_token_upper_bound,
       output_allowance,safety_margin,dispatch_claim_id,dispatch_deadline_at)
      VALUES($1,$2,$3,$4,$5,$6,'offline',$7::jsonb,$8,'jous.text.general.v1','local','model',
       'local','local.v1',$9::jsonb,$10,'non-thinking','LOCAL_PROVISIONAL',$11::jsonb,1,1024,
       3277,$12,$13)""", task_id, organization_id, project_id, user_id, uuid4(), b"a"*32,
        json.dumps(context_package), b"b"*32, json.dumps(request_parameters), b"c"*32,
        json.dumps(token_evidence), claim_id, now + timedelta(seconds=30))
    return task_id


async def create_price(connection):
    price_id = "bind-" + uuid4().hex
    await connection.execute("""INSERT INTO public.route_pricing_versions
      (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,
       input_price_per_1m,output_price_per_1m,provider_fee_applicable,provider_request_fee_usd,
       gateway_fee_applicable,gateway_request_fee_usd,fee_basis_verified,source_type,
       source_evidence_id,reviewed_at,effective_from,valid_until,pricing_status)
      VALUES($1,'route-bind',1,'standard','USD',$2,1,1,true,0,false,NULL,true,
       'manual_review','evidence',now(),now()+interval '2 hours',now()+interval '3 hours','approved')""",
        price_id, BILLING_BASIS)
    return price_id


@unittest.skipUnless(ENABLED, "Explicit disposable PostgreSQL authorization required; never run on managed Dev")
class SnapshotBinding0006DisposableTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_upgrade_rollback_and_all_required_bindings(self):
        import asyncpg
        from alembic import command
        from alembic.config import Config
        from sqlalchemy.ext.asyncio import create_async_engine

        url = disposable_url()
        admin = await asyncpg.connect(url)
        user_id, organization_id, project_id = uuid4(), uuid4(), uuid4()
        task_ids = []
        engine = create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            version = await admin.fetchval("SELECT current_setting('server_version')")
            self.assertTrue(version.startswith("17.11"), version)
            self.assertTrue(await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
            self.assertEqual(await admin.fetchval("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"),
                             "JOUS_V13A_0006_DISPOSABLE_AUTHORIZED")
            self.assertEqual(await admin.fetchval("SELECT version_num FROM public.alembic_version"),
                             "0005_route_economics")

            await admin.execute("INSERT INTO public.users(id) VALUES($1)", user_id)
            await admin.execute("INSERT INTO public.organizations(id,name) VALUES($1,'snapshot-binding-0006')", organization_id)
            await admin.execute("INSERT INTO public.organization_memberships(id,user_id,organization_id,role) VALUES($1,$2,$3,'owner')",
                                uuid4(), user_id, organization_id)
            await admin.execute("INSERT INTO public.projects(id,organization_id,name) VALUES($1,$2,'snapshot-binding-0006')",
                                project_id, organization_id)
            price_id = await create_price(admin)
            now = datetime.now(timezone.utc)
            snapshot = {
                "decision_version": "route-decision.v1", "logical_model_id": "jous.text.general.v1",
                "logical_model_version": 1, "selector_version": "economic.v0",
                "decision_time": now.isoformat(), "input_token_bound": 1, "output_allowance": 1024,
                "selected": {"route_id": "route-bind", "route_version": 1,
                             "pricing_version_id": price_id, "estimated_cost": "0.123", "currency": "USD"},
                "candidate_evaluations": [{"route_id": "route-bind"}],
            }

            async def insert_snapshot(current):
                claim_id = uuid4()
                task_id = await create_task(admin, user_id, organization_id, project_id, claim_id)
                task_ids.append(task_id)
                raw = exact_snapshot_bytes(current)
                await admin.execute(INSERT_DECISION, task_id, organization_id, project_id, user_id,
                                    claim_id, now, price_id, BILLING_BASIS, raw,
                                    hashlib.sha256(raw.encode("utf-8")).digest())
                return task_id

            # Populate every legacy-invalid shape while 0005 still permits UNKNOWN.
            for field in FIELDS:
                absent = copy.deepcopy(snapshot)
                mutate_path(absent, field, remove=True)
                await insert_snapshot(absent)
                explicit_null = copy.deepcopy(snapshot)
                mutate_path(explicit_null, field, value=None)
                await insert_snapshot(explicit_null)

            async def upgrade_once():
                async with engine.connect() as connection:
                    transaction = await connection.begin()
                    try:
                        def run(sync_connection):
                            cfg = Config(str(ROOT / "services/api/alembic.ini"))
                            cfg.attributes["connection"] = sync_connection
                            command.upgrade(cfg, "0006_snapshot_binding")
                        await connection.run_sync(run)
                    except Exception as exc:
                        await transaction.rollback()
                        return exc
                    await transaction.commit()
                    return None

            failed_upgrade = await upgrade_once()
            self.assertIsNotNone(failed_upgrade, "0006 must reject existing UNKNOWN binding rows")
            self.assertEqual(await admin.fetchval("SELECT version_num FROM public.alembic_version"),
                             "0005_route_economics")
            legacy_definition = await admin.fetchval("""SELECT pg_get_constraintdef(oid)
                FROM pg_constraint WHERE conname='ck_route_decisions_snapshot_binding'""")
            self.assertNotIn("IS TRUE", legacy_definition.upper())

            await admin.execute("DELETE FROM public.route_decisions WHERE task_id=ANY($1::uuid[])", task_ids)
            await admin.execute("DELETE FROM public.tasks WHERE id=ANY($1::uuid[])", task_ids)
            task_ids.clear()
            successful_upgrade = await upgrade_once()
            self.assertIsNone(successful_upgrade)
            self.assertEqual(await admin.fetchval("SELECT version_num FROM public.alembic_version"),
                             "0006_snapshot_binding")
            hardened_definition = await admin.fetchval("""SELECT pg_get_constraintdef(oid)
                FROM pg_constraint WHERE conname='ck_route_decisions_snapshot_binding'""")
            self.assertIn("IS TRUE", hardened_definition.upper())

            await insert_snapshot(snapshot)
            self.assertEqual(await admin.fetchval("SELECT count(*) FROM public.route_decisions"), 1)

            for field in FIELDS:
                for label, remove, replacement in (("missing", True, None), ("json-null", False, None)):
                    altered = copy.deepcopy(snapshot)
                    mutate_path(altered, field, remove=remove, value=replacement)
                    with self.subTest(field=field, case=label):
                        with self.assertRaises(asyncpg.CheckViolationError) as caught:
                            await insert_snapshot(altered)
                        self.assertEqual(caught.exception.sqlstate, "23514")
                        self.assertEqual(caught.exception.constraint_name,
                                         "ck_route_decisions_snapshot_binding")

                wrong = copy.deepcopy(snapshot)
                current = wrong
                parts = field.split(".")
                for part in parts[:-1]:
                    current = current[part]
                leaf = parts[-1]
                old = current[leaf]
                if isinstance(old, int):
                    replacement = old + 1
                elif isinstance(old, str) and leaf == "decision_time":
                    replacement = (now + timedelta(seconds=1)).isoformat()
                elif leaf == "estimated_cost":
                    replacement = "0.124"
                else:
                    replacement = "wrong-" + str(old)
                current[leaf] = replacement
                with self.subTest(field=field, case="wrong-value"):
                    with self.assertRaises(asyncpg.CheckViolationError) as caught:
                        await insert_snapshot(wrong)
                    self.assertEqual(caught.exception.sqlstate, "23514")
                    self.assertEqual(caught.exception.constraint_name,
                                     "ck_route_decisions_snapshot_binding")
        finally:
            await engine.dispose()
            await admin.close()


if __name__ == "__main__":
    unittest.main()
