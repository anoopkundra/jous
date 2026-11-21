"""Add source-bound EconomicReceipt and append-only Jous Ledger core."""
from alembic import op


revision = "0009_economic_ledger_core"
down_revision = "0008_usage_event_acl_hardening"
branch_labels = None
depends_on = None


UPGRADE_SQL = (
    "SET LOCAL search_path = pg_catalog",
    "SET LOCAL lock_timeout = '3s'",
    "SET LOCAL statement_timeout = '20s'",
    r"""DO $preflight$
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Migration owner must be postgres'; END IF;
  IF (SELECT count(*) FROM public.alembic_version) <> 1 OR
     (SELECT max(version_num) FROM public.alembic_version) <> '0008_usage_event_acl_hardening' THEN
    RAISE EXCEPTION 'Expected migration revision 0008_usage_event_acl_hardening';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname IN
      ('postgres','jous_runtime','jous_security_reader','jous_economic_processor',
       'anon','authenticated','service_role')) <> 7 THEN
    RAISE EXCEPTION 'Required economic processor or product roles are missing';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
      WHERE r.rolname='jous_economic_processor' AND
       (NOT r.rolcanlogin OR r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR
        r.rolcreaterole OR r.rolreplication OR r.rolinherit)) OR
     EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m
      WHERE m.roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor') OR
            m.member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor')) OR
     pg_catalog.pg_has_role('jous_runtime','jous_economic_processor','MEMBER') THEN
    RAISE EXCEPTION 'Economic processor role attributes or membership are unsafe';
  END IF;
  IF NOT pg_catalog.has_schema_privilege('jous_economic_processor','public','USAGE') THEN
    RAISE EXCEPTION 'Economic processor requires pre-provisioned public schema USAGE';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname IN
        ('economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')) THEN
    RAISE EXCEPTION 'Economic ledger relations already exist';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl d
      CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
      WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
        AND d.defaclobjtype='r' AND d.defaclnamespace=0
        AND a.grantee IN (0,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'))
        AND a.privilege_type IN ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE',
                                 'REFERENCES','TRIGGER','MAINTAIN')) THEN
    RAISE EXCEPTION 'Unsafe global postgres table defaults require separate review';
  END IF;
END
$preflight$""",
    # Role bootstrap is deliberately out of band. Remove only this owner's
    # schema-scoped future table defaults; never recreate unsafe defaults on downgrade.
    "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL PRIVILEGES ON TABLES FROM PUBLIC, anon, authenticated, service_role, jous_runtime, jous_security_reader, jous_economic_processor",
    r"""CREATE TABLE public.supplier_funding_authorities (
      funding_authority_id uuid NOT NULL,
      authority_version integer NOT NULL,
      scope varchar(24) NOT NULL,
      organization_id uuid,
      supplier_id varchar(255) NOT NULL,
      route_id varchar(255) NOT NULL,
      route_version integer NOT NULL,
      credential_authority_ref varchar(255),
      account_owner varchar(16) NOT NULL,
      cost_bearer varchar(24) NOT NULL,
      evidence_type varchar(32) NOT NULL,
      evidence_reference varchar(255) NOT NULL,
      effective_at timestamptz NOT NULL,
      canonical_evidence text NOT NULL,
      authority_digest bytea NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_supplier_funding_authorities PRIMARY KEY (funding_authority_id,authority_version),
      CONSTRAINT fk_supplier_funding_authorities_organization FOREIGN KEY (organization_id)
        REFERENCES public.organizations(id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE,
      CONSTRAINT uq_supplier_funding_authorities_digest_binding UNIQUE (funding_authority_id,authority_version,authority_digest),
      CONSTRAINT ck_supplier_funding_authorities_versions CHECK (authority_version>0 AND route_version>0),
      CONSTRAINT ck_supplier_funding_authorities_scope CHECK (scope IN ('JOUS_GLOBAL','ORGANIZATION')),
      CONSTRAINT ck_supplier_funding_authorities_scope_binding CHECK
        ((scope='JOUS_GLOBAL' AND organization_id IS NULL) OR (scope='ORGANIZATION' AND organization_id IS NOT NULL)),
      CONSTRAINT ck_supplier_funding_authorities_owner CHECK (account_owner IN ('JOUS','CUSTOMER','OTHER','UNKNOWN')),
      CONSTRAINT ck_supplier_funding_authorities_bearer CHECK (cost_bearer IN ('JOUS_BORNE','CUSTOMER_DIRECT','UNKNOWN')),
      CONSTRAINT ck_supplier_funding_authorities_direct_customer CHECK
        (cost_bearer<>'CUSTOMER_DIRECT' OR (scope='ORGANIZATION' AND account_owner='CUSTOMER')),
      CONSTRAINT ck_supplier_funding_authorities_evidence CHECK
        (octet_length(authority_digest)=32 AND length(btrim(supplier_id))>0 AND length(btrim(route_id))>0 AND
         length(btrim(evidence_type))>0 AND length(btrim(evidence_reference))>0 AND
         (credential_authority_ref IS NULL OR length(btrim(credential_authority_ref))>0) AND
         pg_catalog.isfinite(effective_at) AND pg_catalog.isfinite(recorded_at) AND
         canonical_evidence=pg_catalog.jsonb_build_object(
           'schema_version','jous.supplier-funding-authority.v1','funding_authority_id',funding_authority_id,
           'authority_version',authority_version,'scope',scope,'organization_id',organization_id,
           'supplier_id',supplier_id,'route_id',route_id,'route_version',route_version,
           'credential_authority_ref',credential_authority_ref,'account_owner',account_owner,
           'cost_bearer',cost_bearer,'evidence_type',evidence_type,'evidence_reference',evidence_reference,
           'effective_at',pg_catalog.to_char(effective_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))::text AND
         authority_digest=pg_catalog.sha256(pg_catalog.convert_to(canonical_evidence,'UTF8')))
    )""",
    "CREATE INDEX ix_supplier_funding_authorities_org_route ON public.supplier_funding_authorities(organization_id,route_id,route_version,authority_version)",
    "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_id uuid",
    "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_version integer",
    "ALTER TABLE public.route_decisions ADD COLUMN funding_authority_digest bytea",
    "ALTER TABLE public.route_decisions ADD CONSTRAINT fk_route_decisions_funding_authority FOREIGN KEY (funding_authority_id,funding_authority_version,funding_authority_digest) REFERENCES public.supplier_funding_authorities(funding_authority_id,authority_version,authority_digest) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE",
    "ALTER TABLE public.route_decisions ADD CONSTRAINT ck_route_decisions_funding_binding CHECK ((funding_authority_id IS NULL AND funding_authority_version IS NULL AND funding_authority_digest IS NULL) OR (funding_authority_id IS NOT NULL AND funding_authority_version IS NOT NULL AND funding_authority_version>0 AND funding_authority_digest IS NOT NULL AND octet_length(funding_authority_digest)=32))",
    r"""CREATE FUNCTION public.validate_route_funding_authority() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
DECLARE a record;
BEGIN
  IF TG_OP='UPDATE' AND ROW(NEW.funding_authority_id,NEW.funding_authority_version,NEW.funding_authority_digest)
       IS DISTINCT FROM ROW(OLD.funding_authority_id,OLD.funding_authority_version,OLD.funding_authority_digest) THEN
    RAISE EXCEPTION 'Persisted RouteDecision funding binding is immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.funding_authority_id IS NULL THEN
    IF NEW.funding_authority_version IS NOT NULL OR NEW.funding_authority_digest IS NOT NULL THEN
      RAISE EXCEPTION 'Incomplete RouteDecision funding authority binding' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  SELECT scope,organization_id,route_id,route_version,authority_digest
    INTO a FROM public.supplier_funding_authorities
   WHERE funding_authority_id=NEW.funding_authority_id
     AND authority_version=NEW.funding_authority_version;
  IF NOT FOUND OR a.authority_digest IS DISTINCT FROM NEW.funding_authority_digest OR
     a.route_id IS DISTINCT FROM NEW.selected_route_id OR a.route_version IS DISTINCT FROM NEW.selected_route_version OR
     (a.scope='ORGANIZATION' AND a.organization_id IS DISTINCT FROM NEW.organization_id) THEN
    RAISE EXCEPTION 'RouteDecision funding authority scope or route mismatch' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END
$function$""",
    r"""CREATE FUNCTION public.guard_supplier_funding_authority_immutable() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
BEGIN
  RAISE EXCEPTION 'Supplier funding authority versions are immutable' USING ERRCODE='23514';
END
$function$""",
    "CREATE TRIGGER route_decision_funding_authority_guard BEFORE INSERT OR UPDATE OF funding_authority_id,funding_authority_version,funding_authority_digest ON public.route_decisions FOR EACH ROW EXECUTE FUNCTION public.validate_route_funding_authority()",
    "CREATE TRIGGER supplier_funding_authority_immutable BEFORE UPDATE OR DELETE ON public.supplier_funding_authorities FOR EACH ROW EXECUTE FUNCTION public.guard_supplier_funding_authority_immutable()",
    "ALTER TABLE public.executions ADD COLUMN credential_authority_ref varchar(255)",
    "ALTER TABLE public.executions ADD CONSTRAINT ck_executions_credential_authority_ref CHECK (credential_authority_ref IS NULL OR (length(btrim(credential_authority_ref))>0 AND octet_length(credential_authority_ref)<=255))",
    r"""CREATE FUNCTION public.validate_execution_credential_authority() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
DECLARE d record; a record;
BEGIN
  IF TG_OP='UPDATE' AND NEW.credential_authority_ref IS DISTINCT FROM OLD.credential_authority_ref THEN
    RAISE EXCEPTION 'Execution credential authority evidence is immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.credential_authority_ref IS NULL THEN
    IF NEW.request_started_at IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.route_decisions r WHERE r.task_id=NEW.task_id AND r.funding_authority_id IS NOT NULL
    ) THEN
      RAISE EXCEPTION 'Funded dispatch requires actual credential authority evidence' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.request_started_at IS NULL THEN
    RAISE EXCEPTION 'Credential authority evidence requires a dispatched request' USING ERRCODE='23514';
  END IF;
  SELECT funding_authority_id,funding_authority_version,funding_authority_digest,
         organization_id,selected_route_id,selected_route_version
    INTO d FROM public.route_decisions WHERE task_id=NEW.task_id;
  IF NOT FOUND OR d.funding_authority_id IS NULL THEN
    RAISE EXCEPTION 'Execution credential authority has no persisted funding decision' USING ERRCODE='23514';
  END IF;
  SELECT credential_authority_ref,supplier_id,route_id,route_version,scope,organization_id,authority_digest
    INTO a FROM public.supplier_funding_authorities
   WHERE funding_authority_id=d.funding_authority_id AND authority_version=d.funding_authority_version;
  IF NOT FOUND OR d.organization_id IS DISTINCT FROM NEW.organization_id OR
     d.funding_authority_digest IS DISTINCT FROM a.authority_digest OR
     a.credential_authority_ref IS DISTINCT FROM NEW.credential_authority_ref OR
     a.route_id IS DISTINCT FROM d.selected_route_id OR a.route_version IS DISTINCT FROM d.selected_route_version OR
     (a.scope='ORGANIZATION' AND a.organization_id IS DISTINCT FROM NEW.organization_id) THEN
    RAISE EXCEPTION 'Execution credential authority differs from persisted funding decision' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END
$function$""",
    "CREATE TRIGGER executions_credential_authority_guard BEFORE INSERT OR UPDATE OF credential_authority_ref ON public.executions FOR EACH ROW EXECUTE FUNCTION public.validate_execution_credential_authority()",
    r"""CREATE TABLE public.economic_receipts (
      economic_receipt_id uuid NOT NULL,
      assessment_key bytea NOT NULL,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      actor_user_id uuid NOT NULL,
      task_id uuid NOT NULL,
      dispatch_claim_id uuid NOT NULL,
      execution_id uuid NOT NULL,
      usage_event_id uuid NOT NULL,
      route_decision_id uuid,
      pricing_version_id varchar(255),
      funding_authority_id uuid,
      funding_authority_version integer,
      funding_authority_digest bytea,
      economic_policy_version text NOT NULL,
      treatment_policy_digest bytea NOT NULL,
      calculation_version text NOT NULL,
      assessment_status varchar(24) NOT NULL,
      cost_bearer varchar(24) NOT NULL,
      currency char(3) NOT NULL,
      provider_usage_cost_usd numeric(50,18),
      provider_request_fee_usd numeric(50,18),
      gateway_request_fee_usd numeric(50,18),
      computed_usage_cost_usd numeric(50,18),
      pricing_snapshot_canonical text,
      pricing_snapshot_sha256 bytea,
      source_usage_digest bytea NOT NULL,
      canonical_digest bytea NOT NULL,
      supersedes_receipt_id uuid,
      observed_at timestamptz NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_economic_receipts PRIMARY KEY (economic_receipt_id),
      CONSTRAINT uq_economic_receipts_assessment_key UNIQUE (assessment_key),
      CONSTRAINT uq_economic_receipts_single_successor UNIQUE (supersedes_receipt_id),
      CONSTRAINT uq_economic_receipts_ledger_binding UNIQUE
        (economic_receipt_id,organization_id,canonical_digest),
      CONSTRAINT uq_economic_receipts_source_binding UNIQUE
        (economic_receipt_id,usage_event_id,execution_id,task_id,organization_id,
         project_id,actor_user_id,dispatch_claim_id),
      CONSTRAINT fk_economic_receipts_usage_binding FOREIGN KEY
        (usage_event_id,execution_id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        REFERENCES public.usage_events
        (usage_event_id,execution_id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_economic_receipts_route_decision FOREIGN KEY (route_decision_id)
        REFERENCES public.route_decisions(task_id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_economic_receipts_pricing_version FOREIGN KEY (pricing_version_id)
        REFERENCES public.route_pricing_versions(pricing_version_id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_economic_receipts_funding_authority FOREIGN KEY
        (funding_authority_id,funding_authority_version,funding_authority_digest)
        REFERENCES public.supplier_funding_authorities(funding_authority_id,authority_version,authority_digest)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_economic_receipts_supersession_binding FOREIGN KEY
        (supersedes_receipt_id,usage_event_id,execution_id,task_id,organization_id,
         project_id,actor_user_id,dispatch_claim_id)
        REFERENCES public.economic_receipts
        (economic_receipt_id,usage_event_id,execution_id,task_id,organization_id,
         project_id,actor_user_id,dispatch_claim_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT ck_economic_receipts_currency CHECK (currency='USD'),
      CONSTRAINT ck_economic_receipts_status CHECK
        (assessment_status IN ('COMPUTED','INCOMPLETE_USAGE','UNAVAILABLE_USAGE','MISSING_PRICING')),
      CONSTRAINT ck_economic_receipts_bearer CHECK (cost_bearer IN ('JOUS_BORNE','CUSTOMER_DIRECT','UNKNOWN')),
      CONSTRAINT ck_economic_receipts_bearer_authority CHECK (cost_bearer='UNKNOWN' OR funding_authority_id IS NOT NULL),
      CONSTRAINT ck_economic_receipts_digest_lengths CHECK
        (octet_length(assessment_key)=32 AND octet_length(treatment_policy_digest)=32 AND
         octet_length(source_usage_digest)=32 AND octet_length(canonical_digest)=32 AND
         (pricing_snapshot_sha256 IS NULL OR octet_length(pricing_snapshot_sha256)=32) AND
         ((funding_authority_id IS NULL AND funding_authority_version IS NULL AND funding_authority_digest IS NULL) OR
          (funding_authority_id IS NOT NULL AND funding_authority_version IS NOT NULL AND funding_authority_version>0 AND
           funding_authority_digest IS NOT NULL AND octet_length(funding_authority_digest)=32))),
      CONSTRAINT ck_economic_receipts_assessment_key CHECK
        (assessment_key=pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
          'schema_version','jous.economic-assessment.v1','usage_event_id',usage_event_id,
          'economic_policy_version',economic_policy_version,
          'treatment_policy_digest',pg_catalog.encode(treatment_policy_digest,'hex'),
          'calculation_version',calculation_version,'pricing_version_id',pricing_version_id,
          'funding_authority_digest',CASE WHEN funding_authority_digest IS NULL THEN NULL ELSE
            pg_catalog.encode(funding_authority_digest,'hex') END)::text,'UTF8'))),
      CONSTRAINT ck_economic_receipts_pricing_snapshot_digest CHECK
        ((pricing_snapshot_canonical IS NULL)=(pricing_snapshot_sha256 IS NULL) AND
         (pricing_snapshot_canonical IS NULL OR
          pricing_snapshot_sha256=pg_catalog.sha256(pg_catalog.convert_to(pricing_snapshot_canonical,'UTF8')))),
      CONSTRAINT ck_economic_receipts_amount_state CHECK
        ((assessment_status='COMPUTED' AND route_decision_id IS NOT NULL AND pricing_version_id IS NOT NULL AND
          provider_usage_cost_usd IS NOT NULL AND provider_request_fee_usd IS NOT NULL AND
          gateway_request_fee_usd IS NOT NULL AND computed_usage_cost_usd IS NOT NULL AND
          provider_usage_cost_usd>=0 AND provider_request_fee_usd>=0 AND gateway_request_fee_usd>=0 AND
          computed_usage_cost_usd=provider_usage_cost_usd+provider_request_fee_usd+gateway_request_fee_usd AND
          pricing_snapshot_canonical IS NOT NULL AND pricing_snapshot_sha256 IS NOT NULL) OR
         (assessment_status<>'COMPUTED' AND provider_usage_cost_usd IS NULL AND provider_request_fee_usd IS NULL AND
          gateway_request_fee_usd IS NULL AND computed_usage_cost_usd IS NULL)),
      CONSTRAINT ck_economic_receipts_no_self_supersession CHECK
        (supersedes_receipt_id IS NULL OR supersedes_receipt_id<>economic_receipt_id),
      CONSTRAINT ck_economic_receipts_identity CHECK
        (length(btrim(economic_policy_version))>0 AND length(btrim(calculation_version))>0 AND
         pg_catalog.isfinite(observed_at) AND pg_catalog.isfinite(recorded_at))
    )""",
    "CREATE INDEX ix_economic_receipts_org_project_recorded ON public.economic_receipts(organization_id,project_id,recorded_at,economic_receipt_id)",
    r"""CREATE TABLE public.ledger_accounts (
      ledger_account_id uuid NOT NULL,
      account_code varchar(64) NOT NULL,
      economic_classification varchar(64) NOT NULL,
      normal_side varchar(6) NOT NULL,
      currency char(3) NOT NULL,
      postable boolean NOT NULL,
      account_version integer NOT NULL,
      CONSTRAINT pk_ledger_accounts PRIMARY KEY (ledger_account_id),
      CONSTRAINT uq_ledger_accounts_code UNIQUE (account_code),
      CONSTRAINT uq_ledger_accounts_binding UNIQUE (ledger_account_id,currency),
      CONSTRAINT ck_ledger_accounts_currency CHECK (currency='USD'),
      CONSTRAINT ck_ledger_accounts_normal_side CHECK (normal_side IN ('DEBIT','CREDIT')),
      CONSTRAINT ck_ledger_accounts_identity CHECK (account_version>0 AND length(btrim(account_code))>0 AND postable),
      CONSTRAINT ck_ledger_accounts_initial_taxonomy CHECK
        ((account_code='provider_inference_expense' AND economic_classification='PROVIDER_INFERENCE_EXPENSE' AND normal_side='DEBIT') OR
         (account_code='gateway_platform_expense' AND economic_classification='GATEWAY_PLATFORM_EXPENSE' AND normal_side='DEBIT') OR
         (account_code='supplier_cost_accrual' AND economic_classification='SUPPLIER_COST_ACCRUAL' AND normal_side='CREDIT'))
    )""",
    r"""CREATE TABLE public.ledger_transactions (
      ledger_transaction_id uuid NOT NULL,
      organization_id uuid NOT NULL,
      economic_receipt_id uuid NOT NULL,
      posting_purpose varchar(64) NOT NULL,
      idempotency_key bytea NOT NULL,
      currency char(3) NOT NULL,
      source_digest bytea NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_ledger_transactions PRIMARY KEY (ledger_transaction_id),
      CONSTRAINT uq_ledger_transactions_idempotency UNIQUE (idempotency_key),
      CONSTRAINT uq_ledger_transactions_receipt_purpose UNIQUE (economic_receipt_id,posting_purpose),
      CONSTRAINT uq_ledger_transactions_entry_binding UNIQUE (ledger_transaction_id,organization_id,currency),
      CONSTRAINT fk_ledger_transactions_receipt_binding FOREIGN KEY
        (economic_receipt_id,organization_id,source_digest)
        REFERENCES public.economic_receipts(economic_receipt_id,organization_id,canonical_digest)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT ck_ledger_transactions_currency CHECK (currency='USD'),
      CONSTRAINT ck_ledger_transactions_posting_purpose CHECK (posting_purpose='COMPUTED_JOUS_COST_V1'),
      CONSTRAINT ck_ledger_transactions_digest_lengths CHECK (octet_length(idempotency_key)=32 AND octet_length(source_digest)=32),
      CONSTRAINT ck_ledger_transactions_idempotency_identity CHECK
        (idempotency_key=pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
          'schema_version','jous.ledger-posting.v1','economic_receipt_id',economic_receipt_id,
          'posting_purpose',posting_purpose)::text,'UTF8'))),
      CONSTRAINT ck_ledger_transactions_identity CHECK (pg_catalog.isfinite(recorded_at))
    )""",
    r"""CREATE TABLE public.ledger_entries (
      ledger_transaction_id uuid NOT NULL,
      organization_id uuid NOT NULL,
      line_number smallint NOT NULL,
      ledger_account_id uuid NOT NULL,
      currency char(3) NOT NULL,
      direction varchar(6) NOT NULL,
      amount numeric(50,18) NOT NULL,
      CONSTRAINT pk_ledger_entries PRIMARY KEY (ledger_transaction_id,line_number),
      CONSTRAINT uq_ledger_entries_account_direction UNIQUE (ledger_transaction_id,ledger_account_id,direction),
      CONSTRAINT fk_ledger_entries_transaction_binding FOREIGN KEY
        (ledger_transaction_id,organization_id,currency)
        REFERENCES public.ledger_transactions(ledger_transaction_id,organization_id,currency)
        ON DELETE RESTRICT ON UPDATE RESTRICT DEFERRABLE INITIALLY DEFERRED,
      CONSTRAINT fk_ledger_entries_account_currency FOREIGN KEY (ledger_account_id,currency)
        REFERENCES public.ledger_accounts(ledger_account_id,currency)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT ck_ledger_entries_currency CHECK (currency='USD'),
      CONSTRAINT ck_ledger_entries_positive CHECK (line_number>0 AND amount>0),
      CONSTRAINT ck_ledger_entries_direction CHECK (direction IN ('DEBIT','CREDIT'))
    )""",
    "CREATE INDEX ix_ledger_entries_org_transaction ON public.ledger_entries(organization_id,ledger_transaction_id,line_number)",
    "INSERT INTO public.ledger_accounts (ledger_account_id,account_code,economic_classification,normal_side,currency,postable,account_version) VALUES "
      "('b4000000-0000-4000-8000-000000000001','provider_inference_expense','PROVIDER_INFERENCE_EXPENSE','DEBIT','USD',true,1),"
      "('b4000000-0000-4000-8000-000000000002','gateway_platform_expense','GATEWAY_PLATFORM_EXPENSE','DEBIT','USD',true,1),"
      "('b4000000-0000-4000-8000-000000000003','supplier_cost_accrual','SUPPLIER_COST_ACCRUAL','CREDIT','USD',true,1)",
    r"""CREATE FUNCTION public.validate_economic_receipt_source() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
DECLARE u record; d record; p record; a record; e record; snapshot_value jsonb;
  expected_provider_usage numeric; expected_provider_fee numeric; expected_gateway_fee numeric;
BEGIN
  -- Serialize successor creation with the initial ledger-posting decision for
  -- the same immutable receipt. The transaction-scoped key is derived only
  -- from the predecessor identity and uses no elevated database capability.
  IF NEW.supersedes_receipt_id IS NOT NULL THEN
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
      'jous.economic-receipt:' || NEW.supersedes_receipt_id::text, 0));
  END IF;
  SELECT usage_event_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,supplier_id,
         execution_id,route_decision_id,usage_status,input_tokens,output_tokens,evidence_sha256,observed_at
    INTO u FROM public.usage_events WHERE usage_event_id=NEW.usage_event_id;
  IF NOT FOUND OR (NEW.organization_id,NEW.project_id,NEW.actor_user_id,NEW.task_id,
       NEW.execution_id,NEW.dispatch_claim_id,NEW.route_decision_id)
       IS DISTINCT FROM (u.organization_id,u.project_id,u.actor_user_id,u.task_id,
       u.execution_id,u.dispatch_claim_id,u.route_decision_id) THEN
    RAISE EXCEPTION 'Economic receipt source binding mismatch' USING ERRCODE='23503';
  END IF;
  IF NEW.source_usage_digest IS DISTINCT FROM u.evidence_sha256 THEN
    RAISE EXCEPTION 'Economic receipt usage digest mismatch' USING ERRCODE='23514';
  END IF;
  SELECT task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,
         credential_authority_ref,request_started_at
    INTO e FROM public.executions WHERE id=NEW.execution_id;
  IF NOT FOUND OR (e.task_id,e.organization_id,e.project_id,e.actor_user_id,e.dispatch_claim_id)
       IS DISTINCT FROM (NEW.task_id,NEW.organization_id,NEW.project_id,NEW.actor_user_id,NEW.dispatch_claim_id) THEN
    RAISE EXCEPTION 'Economic receipt execution binding mismatch' USING ERRCODE='23503';
  END IF;
  IF NEW.observed_at IS DISTINCT FROM u.observed_at THEN
    RAISE EXCEPTION 'Economic receipt observation time differs from usage evidence' USING ERRCODE='23514';
  END IF;
  IF NEW.assessment_status='COMPUTED' AND u.usage_status<>'AVAILABLE' OR
     NEW.assessment_status='INCOMPLETE_USAGE' AND u.usage_status<>'PARTIAL' OR
     NEW.assessment_status='UNAVAILABLE_USAGE' AND u.usage_status<>'UNAVAILABLE' OR
     NEW.assessment_status='MISSING_PRICING' AND u.usage_status<>'AVAILABLE' THEN
    RAISE EXCEPTION 'Economic receipt status does not match source usage' USING ERRCODE='23514';
  END IF;
  IF u.route_decision_id IS NULL THEN
    IF NEW.pricing_version_id IS NOT NULL OR NEW.pricing_snapshot_canonical IS NOT NULL OR
       NEW.assessment_status='COMPUTED' OR NEW.funding_authority_id IS NOT NULL OR
       NEW.funding_authority_version IS NOT NULL OR NEW.funding_authority_digest IS NOT NULL OR
       NEW.cost_bearer<>'UNKNOWN' OR e.credential_authority_ref IS NOT NULL THEN
      RAISE EXCEPTION 'Legacy source cannot bind pricing evidence' USING ERRCODE='23514';
    END IF;
  ELSE
    SELECT task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,pricing_version_id,
           funding_authority_id,funding_authority_version,funding_authority_digest
      INTO d FROM public.route_decisions WHERE task_id=u.route_decision_id;
    IF NOT FOUND OR d.organization_id<>u.organization_id OR d.project_id<>u.project_id OR
       d.actor_user_id<>u.actor_user_id OR d.dispatch_claim_id<>u.dispatch_claim_id OR
       NEW.route_decision_id IS DISTINCT FROM d.task_id OR
       (NEW.pricing_version_id IS NOT NULL AND NEW.pricing_version_id IS DISTINCT FROM d.pricing_version_id) THEN
      RAISE EXCEPTION 'Economic receipt RouteDecision binding mismatch' USING ERRCODE='23514';
    END IF;
    IF d.funding_authority_id IS NULL THEN
      IF NEW.funding_authority_id IS NOT NULL OR NEW.funding_authority_version IS NOT NULL OR
         NEW.funding_authority_digest IS NOT NULL OR NEW.cost_bearer<>'UNKNOWN' OR
         e.credential_authority_ref IS NOT NULL THEN
        RAISE EXCEPTION 'Unfunded RouteDecision must remain UNKNOWN' USING ERRCODE='23514';
      END IF;
    ELSE
       SELECT scope,organization_id,supplier_id,route_id,route_version,credential_authority_ref,
              account_owner,cost_bearer,authority_digest
        INTO a FROM public.supplier_funding_authorities
       WHERE funding_authority_id=d.funding_authority_id
         AND authority_version=d.funding_authority_version;
       IF NOT FOUND OR a.authority_digest IS DISTINCT FROM d.funding_authority_digest OR
          a.supplier_id IS DISTINCT FROM u.supplier_id OR
          (a.scope='ORGANIZATION' AND a.organization_id IS DISTINCT FROM u.organization_id) OR
          NEW.funding_authority_id IS DISTINCT FROM d.funding_authority_id OR
          NEW.funding_authority_version IS DISTINCT FROM d.funding_authority_version OR
          NEW.funding_authority_digest IS DISTINCT FROM d.funding_authority_digest THEN
        RAISE EXCEPTION 'Economic receipt funding authority/bearer mismatch' USING ERRCODE='23514';
      END IF;
      IF e.credential_authority_ref IS NOT NULL AND
         e.credential_authority_ref IS DISTINCT FROM a.credential_authority_ref THEN
        RAISE EXCEPTION 'Execution credential authority contradicts funding evidence' USING ERRCODE='23514';
      END IF;
      IF (e.credential_authority_ref IS NULL AND
          (e.request_started_at IS NOT NULL OR NEW.cost_bearer<>'UNKNOWN')) OR
         (e.credential_authority_ref IS NOT NULL AND NEW.cost_bearer IS DISTINCT FROM a.cost_bearer) THEN
        RAISE EXCEPTION 'Economic receipt bearer lacks matching dispatch provenance' USING ERRCODE='23514';
      END IF;
      IF NEW.cost_bearer<>'UNKNOWN' AND
         (e.credential_authority_ref IS NULL OR e.request_started_at IS NULL OR
          e.credential_authority_ref IS DISTINCT FROM a.credential_authority_ref) THEN
        RAISE EXCEPTION 'Known cost bearer requires matching dispatched credential evidence' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  IF NEW.assessment_status='COMPUTED' THEN
    IF NEW.route_decision_id IS NULL OR NEW.pricing_version_id IS NULL OR
       NEW.pricing_snapshot_canonical IS NULL OR NEW.pricing_snapshot_sha256 IS NULL THEN
      RAISE EXCEPTION 'Computed receipt requires persisted pricing evidence' USING ERRCODE='23514';
    END IF;
    SELECT pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,
           input_price_per_1m,output_price_per_1m,provider_fee_applicable,
           provider_request_fee_usd,gateway_fee_applicable,gateway_request_fee_usd,
           fee_basis_verified,source_type,source_evidence_id,reviewed_at,effective_from,
           valid_until,pricing_status
      INTO p FROM public.route_pricing_versions WHERE pricing_version_id=NEW.pricing_version_id;
    IF NOT FOUND OR p.pricing_status<>'approved' OR NOT p.fee_basis_verified THEN
      RAISE EXCEPTION 'Computed receipt pricing authority is unavailable' USING ERRCODE='23514';
    END IF;
    snapshot_value := NEW.pricing_snapshot_canonical::jsonb;
    IF pg_catalog.jsonb_typeof(snapshot_value)<>'object' OR
       (SELECT count(*) FROM pg_catalog.jsonb_object_keys(snapshot_value))<>19 OR
       NOT (snapshot_value ?& ARRAY['schema_version','pricing_version_id','route_id','route_version','service_tier',
         'currency','billing_basis','input_price_per_1m','output_price_per_1m','provider_fee_applicable',
         'provider_request_fee_usd','gateway_fee_applicable','gateway_request_fee_usd','fee_basis_verified',
         'source_type','source_evidence_id','reviewed_at','effective_from','valid_until']) OR
       snapshot_value->>'schema_version'<>'jous.route-pricing.v1' OR
       snapshot_value->>'pricing_version_id' IS DISTINCT FROM p.pricing_version_id OR
       snapshot_value->>'route_id' IS DISTINCT FROM p.route_id OR
       (snapshot_value->>'route_version')::integer IS DISTINCT FROM p.route_version OR
       snapshot_value->>'service_tier' IS DISTINCT FROM p.service_tier OR
       snapshot_value->>'currency' IS DISTINCT FROM p.currency OR
       snapshot_value->>'billing_basis' IS DISTINCT FROM p.billing_basis OR
       (snapshot_value->>'input_price_per_1m')::numeric IS DISTINCT FROM p.input_price_per_1m OR
       (snapshot_value->>'output_price_per_1m')::numeric IS DISTINCT FROM p.output_price_per_1m OR
       (snapshot_value->>'provider_fee_applicable')::boolean IS DISTINCT FROM p.provider_fee_applicable OR
       (snapshot_value->>'provider_request_fee_usd')::numeric IS DISTINCT FROM p.provider_request_fee_usd OR
       (snapshot_value->>'gateway_fee_applicable')::boolean IS DISTINCT FROM p.gateway_fee_applicable OR
       (snapshot_value->>'gateway_request_fee_usd')::numeric IS DISTINCT FROM p.gateway_request_fee_usd OR
       (snapshot_value->>'fee_basis_verified')::boolean IS DISTINCT FROM p.fee_basis_verified OR
       snapshot_value->>'source_type' IS DISTINCT FROM p.source_type OR
       snapshot_value->>'source_evidence_id' IS DISTINCT FROM p.source_evidence_id OR
       (snapshot_value->>'reviewed_at')::timestamptz IS DISTINCT FROM p.reviewed_at OR
       (snapshot_value->>'effective_from')::timestamptz IS DISTINCT FROM p.effective_from OR
       (snapshot_value->>'valid_until')::timestamptz IS DISTINCT FROM p.valid_until THEN
      RAISE EXCEPTION 'Pricing snapshot does not match persisted pricing version' USING ERRCODE='23514';
    END IF;
    -- Rates are NUMERIC(20,12), token counts are nonnegative BIGINT, and
    -- division by 1,000,000 therefore yields an exact scale-18 value. Match
    -- the Python Decimal NUMERIC(50,18) contract without any rounding.
    IF u.usage_status<>'AVAILABLE' OR u.input_tokens IS NULL OR u.output_tokens IS NULL THEN
      RAISE EXCEPTION 'Computed receipt requires complete available token evidence' USING ERRCODE='23514';
    END IF;
    expected_provider_usage :=
      (u.input_tokens::numeric * p.input_price_per_1m +
       u.output_tokens::numeric * p.output_price_per_1m) * 0.000001::numeric;
    expected_provider_fee := CASE WHEN p.provider_fee_applicable
      THEN p.provider_request_fee_usd ELSE 0::numeric END;
    expected_gateway_fee := CASE WHEN p.gateway_fee_applicable
      THEN p.gateway_request_fee_usd ELSE 0::numeric END;
    IF NEW.provider_usage_cost_usd IS DISTINCT FROM expected_provider_usage OR
       NEW.provider_request_fee_usd IS DISTINCT FROM expected_provider_fee OR
       NEW.gateway_request_fee_usd IS DISTINCT FROM expected_gateway_fee OR
       NEW.computed_usage_cost_usd IS DISTINCT FROM
         expected_provider_usage + expected_provider_fee + expected_gateway_fee THEN
      RAISE EXCEPTION 'Economic receipt amounts differ from exact UsageEvent/pricing calculation'
        USING ERRCODE='23514';
    END IF;
  ELSIF NEW.pricing_snapshot_canonical IS NOT NULL THEN
    IF NEW.route_decision_id IS NULL OR NEW.pricing_version_id IS NULL THEN
      RAISE EXCEPTION 'Pricing snapshot requires its persisted RouteDecision and version' USING ERRCODE='23514';
    END IF;
  END IF;
  NEW.assessment_key := pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
    'schema_version','jous.economic-assessment.v1','usage_event_id',NEW.usage_event_id,
    'economic_policy_version',NEW.economic_policy_version,
    'treatment_policy_digest',pg_catalog.encode(NEW.treatment_policy_digest,'hex'),
    'calculation_version',NEW.calculation_version,'pricing_version_id',NEW.pricing_version_id,
     'funding_authority_digest',CASE WHEN NEW.funding_authority_digest IS NULL THEN NULL ELSE
       pg_catalog.encode(NEW.funding_authority_digest,'hex') END)::text,'UTF8'));
  NEW.canonical_digest := pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
    'schema_version','jous.economic-receipt.v1','economic_receipt_id',NEW.economic_receipt_id,
    'assessment_key',pg_catalog.encode(NEW.assessment_key,'hex'),'organization_id',NEW.organization_id,
    'project_id',NEW.project_id,'actor_user_id',NEW.actor_user_id,'task_id',NEW.task_id,
    'dispatch_claim_id',NEW.dispatch_claim_id,'execution_id',NEW.execution_id,'usage_event_id',NEW.usage_event_id,
    'route_decision_id',NEW.route_decision_id,'pricing_version_id',NEW.pricing_version_id,
    'funding_authority_id',NEW.funding_authority_id,
    'funding_authority_version',NEW.funding_authority_version,
    'funding_authority_digest',CASE WHEN NEW.funding_authority_digest IS NULL THEN NULL ELSE
      pg_catalog.encode(NEW.funding_authority_digest,'hex') END,
    'economic_policy_version',NEW.economic_policy_version,
    'treatment_policy_digest',pg_catalog.encode(NEW.treatment_policy_digest,'hex'),
    'calculation_version',NEW.calculation_version,'assessment_status',NEW.assessment_status,
    'cost_bearer',NEW.cost_bearer,'currency',NEW.currency,
    'provider_usage_cost_usd',NEW.provider_usage_cost_usd,'provider_request_fee_usd',NEW.provider_request_fee_usd,
    'gateway_request_fee_usd',NEW.gateway_request_fee_usd,'computed_usage_cost_usd',NEW.computed_usage_cost_usd,
    'pricing_snapshot_sha256',CASE WHEN NEW.pricing_snapshot_sha256 IS NULL THEN NULL ELSE pg_catalog.encode(NEW.pricing_snapshot_sha256,'hex') END,
    'source_usage_digest',pg_catalog.encode(NEW.source_usage_digest,'hex'),
    'supersedes_receipt_id',NEW.supersedes_receipt_id,
    'observed_at',pg_catalog.to_char(NEW.observed_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))::text,'UTF8'));
  RETURN NEW;
END
$function$""",
    r"""CREATE FUNCTION public.guard_ledger_entry_insert() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
BEGIN
  IF EXISTS (SELECT 1 FROM public.ledger_transactions
             WHERE ledger_transaction_id=NEW.ledger_transaction_id) THEN
    RAISE EXCEPTION 'Entries must precede immutable transaction header' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END
$function$""",
    r"""CREATE FUNCTION public.validate_ledger_transaction() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
DECLARE tid uuid; org uuid; tx public.ledger_transactions%ROWTYPE; r public.economic_receipts%ROWTYPE;
        n integer; debits numeric(50,18); credits numeric(50,18);
        provider_amount numeric(50,18); gateway_amount numeric(50,18); expected_lines integer;
        provider_lines numeric(50,18); gateway_lines numeric(50,18); accrual_lines numeric(50,18);
        bad_lines integer;
BEGIN
  IF TG_TABLE_NAME='ledger_transactions' THEN tid:=NEW.ledger_transaction_id; org:=NEW.organization_id;
  ELSE tid:=NEW.ledger_transaction_id; org:=NEW.organization_id; END IF;
  SELECT * INTO tx FROM public.ledger_transactions
   WHERE ledger_transaction_id=tid AND organization_id=org;
  IF NOT FOUND THEN RAISE EXCEPTION 'Ledger transaction header missing' USING ERRCODE='23503'; END IF;
  SELECT * INTO r FROM public.economic_receipts
   WHERE economic_receipt_id=tx.economic_receipt_id AND organization_id=tx.organization_id;
  IF NOT FOUND OR r.assessment_status<>'COMPUTED' OR r.cost_bearer<>'JOUS_BORNE' OR
     r.computed_usage_cost_usd IS NULL OR r.computed_usage_cost_usd<=0 OR
     tx.source_digest IS DISTINCT FROM r.canonical_digest OR tx.currency<>r.currency THEN
    RAISE EXCEPTION 'Ledger transaction receipt is not eligible for Jous posting' USING ERRCODE='23514';
  END IF;
  provider_amount:=r.provider_usage_cost_usd+r.provider_request_fee_usd;
  gateway_amount:=r.gateway_request_fee_usd;
  expected_lines:=1+(provider_amount>0)::integer+(gateway_amount>0)::integer;
  SELECT count(*),coalesce(sum(e.amount) FILTER (WHERE e.direction='DEBIT'),0),
         coalesce(sum(e.amount) FILTER (WHERE e.direction='CREDIT'),0),
         coalesce(sum(e.amount) FILTER (WHERE a.account_code='provider_inference_expense' AND e.direction='DEBIT'),0),
         coalesce(sum(e.amount) FILTER (WHERE a.account_code='gateway_platform_expense' AND e.direction='DEBIT'),0),
         coalesce(sum(e.amount) FILTER (WHERE a.account_code='supplier_cost_accrual' AND e.direction='CREDIT'),0),
         count(*) FILTER (WHERE NOT ((a.account_code='provider_inference_expense' AND e.direction='DEBIT') OR
                                    (a.account_code='gateway_platform_expense' AND e.direction='DEBIT') OR
                                    (a.account_code='supplier_cost_accrual' AND e.direction='CREDIT')))
    INTO n,debits,credits,provider_lines,gateway_lines,accrual_lines,bad_lines
    FROM public.ledger_entries e JOIN public.ledger_accounts a ON a.ledger_account_id=e.ledger_account_id
   WHERE e.ledger_transaction_id=tid AND e.organization_id=org AND e.currency=tx.currency;
  IF n<2 OR n<>expected_lines OR debits<>credits OR provider_lines<>provider_amount OR
     gateway_lines<>gateway_amount OR accrual_lines<>r.computed_usage_cost_usd OR bad_lines<>0 THEN
    RAISE EXCEPTION 'Ledger entries do not match receipt economics or balance' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END
$function$""",
    r"""CREATE FUNCTION public.prepare_ledger_transaction() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $function$
DECLARE r public.economic_receipts%ROWTYPE;
BEGIN
  IF pg_catalog.current_setting('transaction_isolation')<>'read committed' THEN
    RAISE EXCEPTION 'Ledger posting requires READ COMMITTED isolation for supersession serialization'
      USING ERRCODE='23514';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'jous.economic-receipt:' || NEW.economic_receipt_id::text, 0));
  SELECT * INTO r FROM public.economic_receipts
   WHERE economic_receipt_id=NEW.economic_receipt_id AND organization_id=NEW.organization_id;
  IF NOT FOUND OR r.assessment_status<>'COMPUTED' OR r.cost_bearer<>'JOUS_BORNE' OR
     r.computed_usage_cost_usd IS NULL OR r.computed_usage_cost_usd<=0 OR
     NEW.posting_purpose<>'COMPUTED_JOUS_COST_V1' OR NEW.currency<>'USD' OR
     NEW.source_digest IS DISTINCT FROM r.canonical_digest THEN
    RAISE EXCEPTION 'Ledger transaction is not eligible for Jous cost posting' USING ERRCODE='23514';
  END IF;
  IF EXISTS (SELECT 1 FROM public.economic_receipts successor
             WHERE successor.supersedes_receipt_id=NEW.economic_receipt_id) THEN
    RAISE EXCEPTION 'Superseded EconomicReceipt cannot originate a new Jous cost posting'
      USING ERRCODE='23514';
  END IF;
  NEW.idempotency_key:=pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
    'schema_version','jous.ledger-posting.v1','economic_receipt_id',NEW.economic_receipt_id,
    'posting_purpose',NEW.posting_purpose)::text,'UTF8'));
  RETURN NEW;
END
$function$""",
    "CREATE TRIGGER economic_receipts_source_guard BEFORE INSERT ON public.economic_receipts FOR EACH ROW EXECUTE FUNCTION public.validate_economic_receipt_source()",
    "CREATE TRIGGER ledger_transactions_source_guard BEFORE INSERT ON public.ledger_transactions FOR EACH ROW EXECUTE FUNCTION public.prepare_ledger_transaction()",
    "CREATE TRIGGER ledger_entries_before_insert BEFORE INSERT ON public.ledger_entries FOR EACH ROW EXECUTE FUNCTION public.guard_ledger_entry_insert()",
    "CREATE CONSTRAINT TRIGGER ledger_entries_balance AFTER INSERT ON public.ledger_entries DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.validate_ledger_transaction()",
    "CREATE CONSTRAINT TRIGGER ledger_transactions_balance AFTER INSERT ON public.ledger_transactions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.validate_ledger_transaction()",
    "ALTER TABLE public.economic_receipts ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.economic_receipts FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.supplier_funding_authorities ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.supplier_funding_authorities FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_accounts ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_accounts FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_transactions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_transactions FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_entries ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.ledger_entries FORCE ROW LEVEL SECURITY",
    "CREATE POLICY supplier_funding_authorities_runtime_select ON public.supplier_funding_authorities AS PERMISSIVE FOR SELECT TO jous_runtime USING (scope='JOUS_GLOBAL' OR (scope='ORGANIZATION' AND organization_id=(CASE WHEN pg_catalog.length(pg_catalog.current_setting('jous.organization_id',true))=36 AND pg_catalog.current_setting('jous.organization_id',true) OPERATOR(pg_catalog.~) '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN CAST(pg_catalog.current_setting('jous.organization_id',true) AS uuid) ELSE NULL END)))",
    "CREATE POLICY supplier_funding_authorities_processor_select ON public.supplier_funding_authorities AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_executions_economic_processor_select ON public.executions AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (EXISTS (SELECT 1 FROM public.usage_events u WHERE u.execution_id=executions.id AND u.task_id=executions.task_id))",
    "CREATE POLICY jous_usage_events_economic_select ON public.usage_events AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_route_decisions_economic_select ON public.route_decisions AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (EXISTS (SELECT 1 FROM public.usage_events u WHERE u.route_decision_id=route_decisions.task_id))",
    "CREATE POLICY jous_route_pricing_economic_select ON public.route_pricing_versions AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (EXISTS (SELECT 1 FROM public.route_decisions d WHERE d.pricing_version_id::text=route_pricing_versions.pricing_version_id::text))",
    "CREATE POLICY jous_economic_receipts_processor_select ON public.economic_receipts AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_economic_receipts_processor_insert ON public.economic_receipts AS PERMISSIVE FOR INSERT TO jous_economic_processor WITH CHECK (EXISTS (SELECT 1 FROM public.usage_events u WHERE u.usage_event_id=economic_receipts.usage_event_id AND u.organization_id=economic_receipts.organization_id AND u.project_id=economic_receipts.project_id AND u.actor_user_id=economic_receipts.actor_user_id AND u.task_id=economic_receipts.task_id AND u.execution_id=economic_receipts.execution_id AND u.dispatch_claim_id=economic_receipts.dispatch_claim_id AND u.route_decision_id IS NOT DISTINCT FROM economic_receipts.route_decision_id))",
    "CREATE POLICY jous_ledger_accounts_processor_select ON public.ledger_accounts AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_ledger_transactions_processor_select ON public.ledger_transactions AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_ledger_transactions_processor_insert ON public.ledger_transactions AS PERMISSIVE FOR INSERT TO jous_economic_processor WITH CHECK (EXISTS (SELECT 1 FROM public.economic_receipts r WHERE r.economic_receipt_id=ledger_transactions.economic_receipt_id AND r.organization_id=ledger_transactions.organization_id AND r.assessment_status='COMPUTED' AND r.cost_bearer='JOUS_BORNE' AND r.computed_usage_cost_usd>0 AND r.canonical_digest=ledger_transactions.source_digest))",
    "CREATE POLICY jous_ledger_entries_processor_select ON public.ledger_entries AS PERMISSIVE FOR SELECT TO jous_economic_processor USING (true)",
    "CREATE POLICY jous_ledger_entries_processor_insert ON public.ledger_entries AS PERMISSIVE FOR INSERT TO jous_economic_processor WITH CHECK (EXISTS (SELECT 1 FROM public.ledger_accounts a WHERE a.ledger_account_id=ledger_entries.ledger_account_id AND a.currency=ledger_entries.currency AND a.postable))",
    "REVOKE ALL PRIVILEGES ON TABLE public.supplier_funding_authorities FROM PUBLIC,anon,authenticated,service_role,jous_runtime,jous_security_reader,jous_economic_processor",
    "REVOKE ALL PRIVILEGES ON TABLE public.economic_receipts,public.ledger_accounts,public.ledger_transactions,public.ledger_entries FROM PUBLIC,anon,authenticated,service_role,jous_runtime,jous_security_reader,jous_economic_processor",
    "REVOKE ALL PRIVILEGES ON TABLE public.executions FROM jous_economic_processor",
    "REVOKE ALL (credential_authority_ref) ON public.executions FROM PUBLIC,anon,authenticated,service_role,jous_runtime,jous_security_reader,jous_economic_processor",
    "REVOKE ALL PRIVILEGES ON TABLE public.usage_events,public.route_decisions,public.route_pricing_versions FROM jous_economic_processor",
    "GRANT SELECT (usage_event_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,execution_id,supplier_id,input_tokens,output_tokens,route_decision_id,usage_status,evidence_sha256,observed_at) ON public.usage_events TO jous_economic_processor",
    "GRANT SELECT (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,pricing_version_id,selected_route_id,selected_route_version,funding_authority_id,funding_authority_version,funding_authority_digest) ON public.route_decisions TO jous_economic_processor",
    "GRANT SELECT (funding_authority_id,authority_version,scope,organization_id,supplier_id,route_id,route_version,credential_authority_ref,account_owner,cost_bearer,evidence_type,evidence_reference,effective_at,canonical_evidence,authority_digest) ON public.supplier_funding_authorities TO jous_economic_processor",
    "GRANT SELECT (funding_authority_id,authority_version,scope,organization_id,supplier_id,route_id,route_version,credential_authority_ref,authority_digest) ON public.supplier_funding_authorities TO jous_runtime",
    "GRANT SELECT (funding_authority_id,funding_authority_version,funding_authority_digest) ON public.route_decisions TO jous_runtime",
    "GRANT SELECT (id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,request_started_at,credential_authority_ref) ON public.executions TO jous_economic_processor",
    "GRANT SELECT (credential_authority_ref) ON public.executions TO jous_runtime",
    "GRANT INSERT (credential_authority_ref) ON public.executions TO jous_runtime",
    "GRANT INSERT (funding_authority_id,funding_authority_version,funding_authority_digest) ON public.route_decisions TO jous_runtime",
    "GRANT SELECT (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,input_price_per_1m,output_price_per_1m,provider_fee_applicable,provider_request_fee_usd,gateway_fee_applicable,gateway_request_fee_usd,fee_basis_verified,source_type,source_evidence_id,reviewed_at,effective_from,valid_until,pricing_status) ON public.route_pricing_versions TO jous_economic_processor",
    "GRANT SELECT ON public.economic_receipts TO jous_economic_processor",
    "GRANT INSERT (economic_receipt_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,execution_id,usage_event_id,route_decision_id,pricing_version_id,funding_authority_id,funding_authority_version,funding_authority_digest,economic_policy_version,treatment_policy_digest,calculation_version,assessment_status,cost_bearer,currency,provider_usage_cost_usd,provider_request_fee_usd,gateway_request_fee_usd,computed_usage_cost_usd,pricing_snapshot_canonical,pricing_snapshot_sha256,source_usage_digest,supersedes_receipt_id,observed_at) ON public.economic_receipts TO jous_economic_processor",
    "GRANT SELECT ON public.ledger_accounts TO jous_economic_processor",
    "GRANT SELECT ON public.ledger_transactions,public.ledger_entries TO jous_economic_processor",
    "GRANT INSERT (ledger_transaction_id,organization_id,economic_receipt_id,posting_purpose,currency,source_digest) ON public.ledger_transactions TO jous_economic_processor",
    "GRANT INSERT (ledger_transaction_id,organization_id,line_number,ledger_account_id,currency,direction,amount) ON public.ledger_entries TO jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.validate_economic_receipt_source() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.validate_route_funding_authority() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.validate_execution_credential_authority() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.guard_supplier_funding_authority_immutable() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.guard_ledger_entry_insert() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.validate_ledger_transaction() FROM PUBLIC,jous_runtime,jous_economic_processor",
    "REVOKE ALL ON FUNCTION public.prepare_ledger_transaction() FROM PUBLIC,jous_runtime,jous_economic_processor",
    r"""DO $postcondition$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='public' AND c.relname IN
         ('supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')
         AND (pg_catalog.pg_get_userbyid(c.relowner)<>'postgres' OR NOT c.relrowsecurity OR NOT c.relforcerowsecurity)) THEN
    RAISE EXCEPTION 'Economic relation owner or FORCE RLS contract failed';
  END IF;
  IF EXISTS (SELECT 1 FROM (VALUES ('anon'),('authenticated'),('service_role'),('jous_runtime'),('jous_security_reader')) r(name)
      CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(priv)
      CROSS JOIN (VALUES ('supplier_funding_authorities'),('economic_receipts'),('ledger_accounts'),('ledger_transactions'),('ledger_entries')) t(name)
      WHERE pg_catalog.has_table_privilege(r.name,'public.'||t.name,p.priv)) THEN
    RAISE EXCEPTION 'Unexpected protected economic relation authority';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
      WHERE a.attrelid='public.supplier_funding_authorities'::regclass AND a.attnum>0 AND NOT a.attisdropped AND
       ((pg_catalog.has_column_privilege('jous_runtime',a.attrelid,a.attnum,'SELECT') IS DISTINCT FROM
           (a.attname::text=ANY(ARRAY['funding_authority_id','authority_version','scope','organization_id','supplier_id','route_id','route_version','credential_authority_ref','authority_digest']))) OR
        (pg_catalog.has_column_privilege('jous_economic_processor',a.attrelid,a.attnum,'SELECT') IS DISTINCT FROM
          (a.attname::text=ANY(ARRAY['funding_authority_id','authority_version','scope','organization_id','supplier_id','route_id','route_version','credential_authority_ref','account_owner','cost_bearer','evidence_type','evidence_reference','effective_at','canonical_evidence','authority_digest']))) OR
        pg_catalog.has_column_privilege('jous_runtime',a.attrelid,a.attnum,'INSERT,UPDATE,REFERENCES') OR
        pg_catalog.has_column_privilege('jous_economic_processor',a.attrelid,a.attnum,'INSERT,UPDATE,REFERENCES'))) THEN
    RAISE EXCEPTION 'Funding authority column privileges exceed the reviewed boundary';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a
      WHERE a.attrelid='public.executions'::regclass AND a.attnum>0 AND NOT a.attisdropped AND
        (pg_catalog.has_column_privilege('jous_runtime',a.attrelid,a.attnum,'SELECT') IS DISTINCT FROM
           (a.attname::text=ANY(ARRAY['id','task_id','organization_id','project_id','actor_user_id','dispatch_claim_id','status','response_text','reported_model_id','reported_provider_id','provider_request_id','provider_response_id','finish_reason','usage','usage_status','error_code','request_started_at','response_received_at','credential_authority_ref','recorded_at'])) OR
         pg_catalog.has_column_privilege('jous_runtime',a.attrelid,a.attnum,'INSERT') IS DISTINCT FROM
           (a.attname::text=ANY(ARRAY['id','task_id','organization_id','project_id','actor_user_id','dispatch_claim_id','status','response_text','reported_model_id','reported_provider_id','provider_request_id','provider_response_id','finish_reason','usage','usage_status','error_code','request_started_at','response_received_at','credential_authority_ref'])) OR
         pg_catalog.has_column_privilege('jous_economic_processor',a.attrelid,a.attnum,'SELECT') IS DISTINCT FROM
           (a.attname::text=ANY(ARRAY['id','task_id','organization_id','project_id','actor_user_id','dispatch_claim_id','request_started_at','credential_authority_ref'])) OR
         pg_catalog.has_column_privilege('jous_runtime',a.attrelid,a.attnum,'UPDATE,REFERENCES') OR
         pg_catalog.has_column_privilege('jous_economic_processor',a.attrelid,a.attnum,'INSERT,UPDATE,REFERENCES'))) THEN
    RAISE EXCEPTION 'Execution credential authority column privileges exceed the reviewed boundary';
  END IF;
  IF EXISTS (SELECT 1 FROM (VALUES ('supplier_funding_authorities'),('economic_receipts'),('ledger_accounts'),('ledger_transactions'),('ledger_entries')) t(name)
      CROSS JOIN (VALUES ('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(priv)
      WHERE pg_catalog.has_table_privilege('jous_economic_processor','public.'||t.name,p.priv)) OR
     NOT pg_catalog.has_table_privilege('jous_economic_processor','public.economic_receipts','SELECT') OR
     pg_catalog.has_table_privilege('jous_economic_processor','public.economic_receipts','INSERT') OR
     NOT pg_catalog.has_table_privilege('jous_economic_processor','public.ledger_accounts','SELECT') OR
     pg_catalog.has_table_privilege('jous_economic_processor','public.ledger_entries','INSERT') OR
     pg_catalog.has_table_privilege('jous_economic_processor','public.ledger_transactions','INSERT') OR
     NOT pg_catalog.has_any_column_privilege('jous_economic_processor','public.economic_receipts','INSERT') OR
      NOT pg_catalog.has_any_column_privilege('jous_economic_processor','public.ledger_entries','INSERT') OR
      NOT pg_catalog.has_any_column_privilege('jous_economic_processor','public.ledger_transactions','INSERT') OR
      pg_catalog.has_table_privilege('jous_economic_processor','public.supplier_funding_authorities','INSERT') OR
      pg_catalog.has_table_privilege('jous_runtime','public.supplier_funding_authorities','INSERT') OR
      pg_catalog.has_table_privilege('jous_economic_processor','public.supplier_funding_authorities','UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
      pg_catalog.has_table_privilege('jous_runtime','public.supplier_funding_authorities','UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
      NOT pg_catalog.has_any_column_privilege('jous_economic_processor','public.supplier_funding_authorities','SELECT') OR
       pg_catalog.has_column_privilege('jous_runtime','public.supplier_funding_authorities','cost_bearer','SELECT') OR
       NOT pg_catalog.has_column_privilege('jous_runtime','public.supplier_funding_authorities','credential_authority_ref','SELECT') OR
      pg_catalog.has_column_privilege('jous_economic_processor','public.supplier_funding_authorities','recorded_at','SELECT') OR
      pg_catalog.has_schema_privilege('jous_economic_processor','public','CREATE') OR
      pg_catalog.pg_has_role('jous_runtime','jous_economic_processor','MEMBER') OR
      pg_catalog.has_table_privilege('jous_economic_processor','public.executions','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN') OR
      pg_catalog.has_column_privilege('jous_economic_processor','public.executions','credential_authority_ref','INSERT,UPDATE,REFERENCES') THEN
    RAISE EXCEPTION 'Economic processor privilege contract failed';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl d CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
      WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres') AND
        d.defaclobjtype='r' AND d.defaclnamespace IN (0,(SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='public')) AND
        a.grantee IN (0,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_security_reader'),
          (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_economic_processor'))) THEN
    RAISE EXCEPTION 'Unsafe postgres/public future table defaults remain';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='public' AND p.proname IN ('validate_economic_receipt_source','validate_route_funding_authority',
          'validate_execution_credential_authority',
         'guard_supplier_funding_authority_immutable','guard_ledger_entry_insert',
         'validate_ledger_transaction','prepare_ledger_transaction') AND p.prosecdef) THEN
    RAISE EXCEPTION 'Economic invariant function must remain SECURITY INVOKER';
  END IF;
END
$postcondition$""",
)


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    # Economic receipts and posted journal evidence are append-only history.
    # Never drop them or reconstruct inherited unsafe privileges.
    pass
