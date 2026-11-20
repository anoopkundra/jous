"""Add reviewed route prices, append-only revocations, and task-bound decisions."""
from alembic import op

revision = "0005_route_economics"
down_revision = "0004_product_acl_hardening"
branch_labels = depends_on = None

UPGRADE_SQL = (
    "SET LOCAL search_path = pg_catalog",
    "SET LOCAL lock_timeout = '3s'",
    "SET LOCAL statement_timeout = '15s'",
    r"""DO $preflight$
DECLARE task_owner name; task_kind "char"; binding_ok boolean;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Migration owner must be postgres'; END IF;
  IF (SELECT count(*) FROM public.alembic_version) <> 1 OR
     (SELECT max(version_num) FROM public.alembic_version) <> '0004_product_acl_hardening' THEN
    RAISE EXCEPTION 'Expected migration revision 0004_product_acl_hardening';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname IN ('postgres','jous_runtime','jous_security_reader')) <> 3 THEN
    RAISE EXCEPTION 'Required product roles are missing';
  END IF;
  SELECT c.relowner::regrole::text::name, c.relkind INTO task_owner, task_kind
  FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname='tasks';
  IF task_owner IS DISTINCT FROM 'postgres' OR task_kind IS DISTINCT FROM 'r' THEN
    RAISE EXCEPTION 'Expected postgres-owned ordinary public.tasks';
  END IF;
  SELECT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint c
    WHERE c.conrelid='public.tasks'::regclass AND c.conname='uq_tasks_execution_binding'
      AND c.contype='u' AND NOT c.condeferrable AND c.convalidated
      AND (SELECT array_agg(a.attname::text ORDER BY k.ord)
           FROM unnest(c.conkey) WITH ORDINALITY k(attnum,ord)
           JOIN pg_catalog.pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum) =
          ARRAY['id','organization_id','project_id','actor_user_id','dispatch_claim_id']::text[]
  ) INTO binding_ok;
  IF NOT binding_ok THEN RAISE EXCEPTION 'V1.2 task binding constraint is missing or changed'; END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relname IN
             ('route_pricing_versions','route_pricing_revocations','route_decisions')) THEN
    RAISE EXCEPTION 'A V1.3 route-economics object already exists';
  END IF;
END
$preflight$""",
    """CREATE TABLE public.route_pricing_versions (
      pricing_version_id varchar(255) NOT NULL,
      route_id varchar(255) NOT NULL,
      route_version integer NOT NULL,
      service_tier varchar(255) NOT NULL,
      currency varchar(3) NOT NULL,
      billing_basis varchar(64) NOT NULL,
      input_price_per_1m numeric(20,12) NOT NULL,
      output_price_per_1m numeric(20,12) NOT NULL,
      provider_fee_applicable boolean NOT NULL,
      provider_request_fee_usd numeric(20,12),
      gateway_fee_applicable boolean NOT NULL,
      gateway_request_fee_usd numeric(20,12),
      fee_basis_verified boolean NOT NULL,
      source_type varchar(32) NOT NULL,
      source_evidence_id varchar(255) NOT NULL,
      reviewed_at timestamptz NOT NULL,
      effective_from timestamptz NOT NULL,
      valid_until timestamptz NOT NULL,
      pricing_status varchar(16) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_route_pricing_versions PRIMARY KEY (pricing_version_id),
      CONSTRAINT uq_route_pricing_identity UNIQUE
        (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis),
      CONSTRAINT ck_route_pricing_version_positive CHECK (route_version > 0),
      CONSTRAINT ck_route_pricing_currency CHECK (currency='USD'),
      CONSTRAINT ck_route_pricing_billing CHECK (billing_basis='input_output_tokens_plus_request_fees_v1'),
      CONSTRAINT ck_route_pricing_rates CHECK (input_price_per_1m >= 0 AND output_price_per_1m >= 0),
      CONSTRAINT ck_route_pricing_provider_fee CHECK
        ((provider_fee_applicable AND (provider_request_fee_usd IS NULL OR provider_request_fee_usd >= 0))
         OR (NOT provider_fee_applicable AND provider_request_fee_usd IS NULL)),
      CONSTRAINT ck_route_pricing_gateway_fee CHECK
        ((gateway_fee_applicable AND (gateway_request_fee_usd IS NULL OR gateway_request_fee_usd >= 0))
         OR (NOT gateway_fee_applicable AND gateway_request_fee_usd IS NULL)),
      CONSTRAINT ck_route_pricing_approval CHECK
        (pricing_status IN ('pending','approved') AND
         (pricing_status <> 'approved' OR (fee_basis_verified AND
          ((provider_fee_applicable AND provider_request_fee_usd IS NOT NULL) OR
           (NOT provider_fee_applicable AND provider_request_fee_usd IS NULL)) AND
          ((gateway_fee_applicable AND gateway_request_fee_usd IS NOT NULL) OR
           (NOT gateway_fee_applicable AND gateway_request_fee_usd IS NULL))))),
      CONSTRAINT ck_route_pricing_source CHECK
        (source_type IN ('provider_published','gateway_published','invoice_review','manual_review')),
      CONSTRAINT ck_route_pricing_evidence CHECK
        (length(btrim(pricing_version_id))>0 AND length(btrim(route_id))>0 AND
         length(btrim(service_tier))>0 AND length(btrim(source_evidence_id))>0 AND
         pg_catalog.isfinite(reviewed_at) AND pg_catalog.isfinite(effective_from) AND
         pg_catalog.isfinite(valid_until) AND valid_until>effective_from)
    )""",
    """CREATE TABLE public.route_pricing_revocations (
      pricing_version_id varchar(255) NOT NULL,
      revoked_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      reason_code varchar(64) NOT NULL,
      evidence_id varchar(255) NOT NULL,
      CONSTRAINT pk_route_pricing_revocations PRIMARY KEY (pricing_version_id),
      CONSTRAINT fk_route_pricing_revocation_version FOREIGN KEY (pricing_version_id)
        REFERENCES public.route_pricing_versions(pricing_version_id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE,
      CONSTRAINT ck_route_pricing_revocation_fields CHECK
        (pg_catalog.isfinite(revoked_at) AND length(btrim(reason_code))>0 AND length(btrim(evidence_id))>0)
    )""",
    """CREATE TABLE public.route_decisions (
      task_id uuid NOT NULL,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      actor_user_id uuid NOT NULL,
      dispatch_claim_id uuid NOT NULL,
      decision_version varchar(255) NOT NULL,
      selector_version varchar(255) NOT NULL,
      logical_model_id varchar(255) NOT NULL,
      logical_model_version integer NOT NULL,
      decided_at timestamptz NOT NULL,
      pricing_version_id varchar(255) NOT NULL,
      selected_route_id varchar(255) NOT NULL,
      selected_route_version integer NOT NULL,
      service_tier varchar(255) NOT NULL,
      currency varchar(3) NOT NULL,
      billing_basis varchar(64) NOT NULL,
      input_token_bound integer NOT NULL,
      output_allowance integer NOT NULL,
      estimated_cost_usd numeric(38,18) NOT NULL,
      decision_snapshot text NOT NULL,
      snapshot_sha256 bytea NOT NULL,
      created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_route_decisions PRIMARY KEY (task_id),
      CONSTRAINT uq_route_decisions_dispatch_claim UNIQUE (dispatch_claim_id),
      CONSTRAINT fk_route_decisions_task_binding FOREIGN KEY
        (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        REFERENCES public.tasks(id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE,
      CONSTRAINT fk_route_decisions_pricing FOREIGN KEY
        (pricing_version_id,selected_route_id,selected_route_version,service_tier,currency,billing_basis)
        REFERENCES public.route_pricing_versions
        (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE,
      CONSTRAINT ck_route_decisions_snapshot CHECK
        (octet_length(decision_snapshot) BETWEEN 1 AND 65536 AND
         pg_catalog.jsonb_typeof(decision_snapshot::jsonb)='object' AND
         pg_catalog.jsonb_typeof(decision_snapshot::jsonb->'selected')='object' AND
         pg_catalog.jsonb_typeof(decision_snapshot::jsonb->'candidate_evaluations')='array' AND
         pg_catalog.jsonb_array_length(decision_snapshot::jsonb->'candidate_evaluations') BETWEEN 1 AND 64),
      CONSTRAINT ck_route_decisions_snapshot_binding CHECK
        ((decision_snapshot::jsonb->>'decision_version')=decision_version AND
         (decision_snapshot::jsonb->>'logical_model_id')=logical_model_id AND
         (decision_snapshot::jsonb->>'logical_model_version')::integer=logical_model_version AND
         (decision_snapshot::jsonb->>'selector_version')=selector_version AND
         (decision_snapshot::jsonb->>'decision_time')::timestamptz=decided_at AND
         (decision_snapshot::jsonb->>'input_token_bound')::integer=input_token_bound AND
         (decision_snapshot::jsonb->>'output_allowance')::integer=output_allowance AND
         decision_snapshot::jsonb->'selected'->>'route_id'=selected_route_id AND
         (decision_snapshot::jsonb->'selected'->>'route_version')::integer=selected_route_version AND
         decision_snapshot::jsonb->'selected'->>'pricing_version_id'=pricing_version_id AND
         (decision_snapshot::jsonb->'selected'->>'estimated_cost')::numeric=estimated_cost_usd AND
         decision_snapshot::jsonb->'selected'->>'currency'=currency),
      CONSTRAINT ck_route_decisions_hash CHECK (octet_length(snapshot_sha256)=32),
      CONSTRAINT ck_route_decisions_snapshot_digest CHECK
        (snapshot_sha256=pg_catalog.sha256(pg_catalog.convert_to(decision_snapshot,'UTF8'))),
      CONSTRAINT ck_route_decisions_currency CHECK (currency='USD'),
      CONSTRAINT ck_route_decisions_route_version CHECK (selected_route_version>0 AND logical_model_version>0),
      CONSTRAINT ck_route_decisions_token_bounds CHECK
        (input_token_bound BETWEEN 0 AND 2147483647 AND output_allowance BETWEEN 0 AND 2147483647),
      CONSTRAINT ck_route_decisions_estimate CHECK (estimated_cost_usd>=0),
      CONSTRAINT ck_route_decisions_identity CHECK
        (length(btrim(decision_version))>0 AND length(btrim(selector_version))>0 AND
         length(btrim(logical_model_id))>0 AND pg_catalog.isfinite(decided_at))
    )""",
    "CREATE INDEX ix_route_pricing_lookup ON public.route_pricing_versions(route_id,route_version,service_tier,currency,billing_basis,pricing_status,effective_from,valid_until)",
    "CREATE INDEX ix_route_pricing_source_time ON public.route_pricing_versions(source_evidence_id,reviewed_at)",
    "CREATE INDEX ix_route_decisions_project_time ON public.route_decisions(organization_id,project_id,created_at DESC,task_id)",
    "ALTER TABLE public.route_pricing_versions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.route_pricing_versions FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.route_pricing_revocations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.route_pricing_revocations FORCE ROW LEVEL SECURITY",
    "ALTER TABLE public.route_decisions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.route_decisions FORCE ROW LEVEL SECURITY",
    "CREATE POLICY jous_route_pricing_select ON public.route_pricing_versions AS PERMISSIVE FOR SELECT TO jous_runtime USING (pricing_status='approved' AND NOT EXISTS (SELECT 1 FROM public.route_pricing_revocations r WHERE r.pricing_version_id=route_pricing_versions.pricing_version_id))",
    "CREATE POLICY jous_route_revocations_select ON public.route_pricing_revocations AS PERMISSIVE FOR SELECT TO jous_runtime USING (true)",
    "CREATE POLICY jous_route_decisions_select ON public.route_decisions AS PERMISSIVE FOR SELECT TO jous_runtime USING (EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=route_decisions.task_id AND t.organization_id=route_decisions.organization_id AND t.project_id=route_decisions.project_id AND t.actor_user_id=route_decisions.actor_user_id AND t.dispatch_claim_id=route_decisions.dispatch_claim_id))",
    "CREATE POLICY jous_route_decisions_insert ON public.route_decisions AS PERMISSIVE FOR INSERT TO jous_runtime WITH CHECK (EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=route_decisions.task_id AND t.organization_id=route_decisions.organization_id AND t.project_id=route_decisions.project_id AND t.actor_user_id=route_decisions.actor_user_id AND t.dispatch_claim_id=route_decisions.dispatch_claim_id) AND EXISTS (SELECT 1 FROM public.route_pricing_versions p WHERE p.pricing_version_id=route_decisions.pricing_version_id AND p.route_id=route_decisions.selected_route_id AND p.route_version=route_decisions.selected_route_version AND p.service_tier=route_decisions.service_tier AND p.currency=route_decisions.currency AND p.billing_basis=route_decisions.billing_basis))",
    r"""CREATE FUNCTION public.enforce_route_price_interval() RETURNS trigger
      LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog AS $price_overlap$
      DECLARE lock_key bigint;
      BEGIN
        IF NEW.pricing_status <> 'approved' THEN RETURN NEW; END IF;
        lock_key := pg_catalog.hashtextextended(
          pg_catalog.jsonb_build_array(NEW.route_id,NEW.route_version,NEW.service_tier,NEW.currency,NEW.billing_basis)::text,0);
        PERFORM pg_catalog.pg_advisory_xact_lock(lock_key);
        IF EXISTS (
          SELECT 1 FROM public.route_pricing_versions p
          WHERE p.route_id=NEW.route_id AND p.route_version=NEW.route_version
            AND p.service_tier=NEW.service_tier AND p.currency=NEW.currency AND p.billing_basis=NEW.billing_basis
            AND p.pricing_status='approved'
            AND NEW.effective_from < p.valid_until AND p.effective_from < NEW.valid_until
            AND NOT EXISTS (SELECT 1 FROM public.route_pricing_revocations r WHERE r.pricing_version_id=p.pricing_version_id)
        ) THEN RAISE EXCEPTION 'Overlapping approved route price interval' USING ERRCODE='23505'; END IF;
        RETURN NEW;
      END $price_overlap$""",
    "CREATE TRIGGER trg_route_price_interval BEFORE INSERT ON public.route_pricing_versions FOR EACH ROW EXECUTE FUNCTION public.enforce_route_price_interval()",
    "REVOKE ALL PRIVILEGES ON TABLE public.route_pricing_versions, public.route_pricing_revocations, public.route_decisions FROM PUBLIC",
    "REVOKE ALL PRIVILEGES ON TABLE public.route_pricing_versions, public.route_pricing_revocations, public.route_decisions FROM jous_runtime, jous_security_reader",
    "REVOKE ALL PRIVILEGES ON FUNCTION public.enforce_route_price_interval() FROM PUBLIC, jous_runtime, jous_security_reader",
    r"""DO $acl_hardening$
DECLARE target record; grantee_oid oid; grantee_sql text; grantee_name name;
BEGIN
  FOR target IN SELECT c.oid,c.relname,c.relowner,c.relacl FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions') AND c.relkind='r'
  LOOP
    FOR grantee_oid IN SELECT DISTINCT x.grantee FROM pg_catalog.aclexplode(
      COALESCE(target.relacl,pg_catalog.acldefault('r',target.relowner))) x WHERE x.grantee<>target.relowner
    LOOP
      IF grantee_oid=0 THEN grantee_sql := 'PUBLIC';
      ELSE
        SELECT r.rolname INTO grantee_name FROM pg_catalog.pg_roles r WHERE r.oid=grantee_oid;
        IF grantee_name IS NULL THEN RAISE EXCEPTION 'Missing relation ACL grantee'; END IF;
        grantee_sql := pg_catalog.quote_ident(grantee_name::text);
      END IF;
      EXECUTE pg_catalog.format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %s',target.relname,grantee_sql);
    END LOOP;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
      LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) x
      WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
      AND c.relkind='r' AND x.grantee<>c.relowner) THEN RAISE EXCEPTION 'Non-owner route-economics ACL remains'; END IF;
END $acl_hardening$""",
    r"""DO $column_acl_hardening$
DECLARE target record; column_name name; grantee_oid oid; grantee_sql text; grantee_name name;
BEGIN
  FOR target IN SELECT c.oid,c.relname,c.relowner FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions') AND c.relkind='r'
  LOOP
    FOR column_name IN SELECT a.attname FROM pg_catalog.pg_attribute a
      WHERE a.attrelid=target.oid AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum
    LOOP
      FOR grantee_oid IN SELECT DISTINCT x.grantee FROM pg_catalog.pg_attribute a,
        LATERAL pg_catalog.aclexplode(a.attacl) x
        WHERE a.attrelid=target.oid AND a.attname=column_name AND x.grantee<>target.relowner
      LOOP
        IF grantee_oid=0 THEN grantee_sql := 'PUBLIC';
        ELSE
          SELECT r.rolname INTO grantee_name FROM pg_catalog.pg_roles r WHERE r.oid=grantee_oid;
          IF grantee_name IS NULL THEN RAISE EXCEPTION 'Missing column ACL grantee'; END IF;
          grantee_sql := pg_catalog.quote_ident(grantee_name::text);
        END IF;
        EXECUTE pg_catalog.format('REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM %s',column_name,target.relname,grantee_sql);
      END LOOP;
    END LOOP;
  END LOOP;
END $column_acl_hardening$""",
    r"""DO $function_acl_hardening$
DECLARE function_oid oid; function_owner oid; function_acl aclitem[];
        grantee_oid oid; grantee_sql text; grantee_name name;
BEGIN
  SELECT p.oid,p.proowner,p.proacl INTO function_oid,function_owner,function_acl
  FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public' AND p.proname='enforce_route_price_interval'
    AND pg_catalog.pg_get_function_identity_arguments(p.oid)='';
  IF function_oid IS NULL OR function_owner<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres') THEN
    RAISE EXCEPTION 'Expected postgres-owned route price trigger function';
  END IF;
  FOR grantee_oid IN SELECT DISTINCT a.grantee FROM pg_catalog.aclexplode(
    COALESCE(function_acl,pg_catalog.acldefault('f',function_owner))) a WHERE a.grantee<>function_owner
  LOOP
    IF grantee_oid=0 THEN grantee_sql := 'PUBLIC';
    ELSE
      SELECT r.rolname INTO grantee_name FROM pg_catalog.pg_roles r WHERE r.oid=grantee_oid;
      IF grantee_name IS NULL THEN RAISE EXCEPTION 'Missing function ACL grantee'; END IF;
      grantee_sql := pg_catalog.quote_ident(grantee_name::text);
    END IF;
    EXECUTE pg_catalog.format('REVOKE ALL PRIVILEGES ON FUNCTION public.enforce_route_price_interval() FROM %s',grantee_sql);
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
      LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
      WHERE n.nspname='public' AND p.proname='enforce_route_price_interval' AND a.grantee<>p.proowner)
    THEN RAISE EXCEPTION 'Non-owner trigger-function ACL remains'; END IF;
END $function_acl_hardening$""",
    "GRANT SELECT (pricing_version_id,route_id,route_version,service_tier,currency,billing_basis,input_price_per_1m,output_price_per_1m,provider_fee_applicable,provider_request_fee_usd,gateway_fee_applicable,gateway_request_fee_usd,fee_basis_verified,source_type,source_evidence_id,reviewed_at,effective_from,valid_until,pricing_status,created_at) ON public.route_pricing_versions TO jous_runtime",
    "GRANT SELECT (pricing_version_id) ON public.route_pricing_revocations TO jous_runtime",
    "GRANT SELECT (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,decision_version,selector_version,logical_model_id,logical_model_version,decided_at,pricing_version_id,selected_route_id,selected_route_version,service_tier,currency,billing_basis,input_token_bound,output_allowance,estimated_cost_usd,decision_snapshot,snapshot_sha256,created_at) ON public.route_decisions TO jous_runtime",
    "GRANT INSERT (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,decision_version,selector_version,logical_model_id,logical_model_version,decided_at,pricing_version_id,selected_route_id,selected_route_version,service_tier,currency,billing_basis,input_token_bound,output_allowance,estimated_cost_usd,decision_snapshot,snapshot_sha256) ON public.route_decisions TO jous_runtime",
    r"""DO $postcondition$
DECLARE object_count integer; policy_names text[];
BEGIN
  SELECT count(*) INTO object_count FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
      AND c.relkind='r' AND c.relowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
      AND c.relrowsecurity AND c.relforcerowsecurity;
  IF object_count<>3 THEN RAISE EXCEPTION 'Route-economics owner/RLS postcondition failed'; END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
      LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
      WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
       AND a.grantee<>c.relowner) THEN RAISE EXCEPTION 'Non-owner relation ACL remains'; END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_attribute x ON x.attrelid=c.oid,LATERAL pg_catalog.aclexplode(x.attacl) a
      WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
       AND x.attnum>0 AND NOT x.attisdropped AND
       (a.grantee<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime') OR a.is_grantable))
      THEN RAISE EXCEPTION 'Unexpected route-economics column ACL remains'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
    CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(priv)
    WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
      AND a.attnum>0 AND NOT a.attisdropped
      AND pg_catalog.has_column_privilege('jous_runtime',c.oid,a.attnum,p.priv) IS DISTINCT FROM
        CASE WHEN p.priv='SELECT' THEN
          c.relname IN ('route_pricing_versions','route_decisions') OR
          (c.relname='route_pricing_revocations' AND a.attname='pricing_version_id')
        WHEN p.priv='INSERT' THEN c.relname='route_decisions' AND a.attname<>'created_at'
        ELSE false END
  ) THEN RAISE EXCEPTION 'Runtime column privilege matrix mismatch'; END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(priv)
      WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions')
       AND a.attnum>0 AND NOT a.attisdropped AND pg_catalog.has_column_privilege('jous_security_reader',c.oid,a.attnum,p.priv))
      THEN RAISE EXCEPTION 'Security reader has route-economics column access'; END IF;
  SELECT array_agg(p.polname::text ORDER BY p.polname) INTO policy_names FROM pg_catalog.pg_policy p
    JOIN pg_catalog.pg_class c ON c.oid=p.polrelid JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('route_pricing_versions','route_pricing_revocations','route_decisions');
  IF policy_names IS DISTINCT FROM ARRAY['jous_route_decisions_insert','jous_route_decisions_select',
      'jous_route_pricing_select','jous_route_revocations_select']::text[]
      THEN RAISE EXCEPTION 'Route-economics policy postcondition failed'; END IF;
END $postcondition$""",
)


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    # Route/pricing decisions are audit evidence; unknown grants must not be reconstructed.
    pass
