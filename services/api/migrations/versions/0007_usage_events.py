"""Persist immutable normalized usage evidence for terminal executions."""
from alembic import op


revision = "0007_usage_events"
down_revision = "0006_snapshot_binding"
branch_labels = None
depends_on = None


UPGRADE_SQL = (
    "SET LOCAL search_path = pg_catalog",
    "SET LOCAL lock_timeout = '3s'",
    "SET LOCAL statement_timeout = '15s'",
    r"""DO $preflight$
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Migration owner must be postgres'; END IF;
  IF (SELECT count(*) FROM public.alembic_version) <> 1 OR
     (SELECT max(version_num) FROM public.alembic_version) <> '0006_snapshot_binding' THEN
    RAISE EXCEPTION 'Expected migration revision 0006_snapshot_binding';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname IN ('postgres','jous_runtime','jous_security_reader')) <> 3 THEN
    RAISE EXCEPTION 'Required product roles are missing';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relname='usage_events') THEN
    RAISE EXCEPTION 'V1.4 UsageEvent relation already exists';
  END IF;
END
$preflight$""",
    """CREATE TABLE public.usage_events (
      usage_event_id uuid NOT NULL,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      actor_user_id uuid NOT NULL,
      task_id uuid NOT NULL,
      dispatch_claim_id uuid NOT NULL,
      execution_id uuid NOT NULL,
      route_decision_id uuid,
      logical_model_id varchar(255) NOT NULL,
      logical_model_version integer,
      route_id varchar(255),
      route_version integer,
      supplier_id varchar(255) NOT NULL,
      underlying_provider varchar(255) NOT NULL,
      reported_provider_id varchar(255),
      input_tokens bigint,
      output_tokens bigint,
      total_tokens bigint,
      cached_input_tokens bigint,
      reasoning_tokens bigint,
      usage_status varchar(16) NOT NULL,
      source_type varchar(32) NOT NULL,
      source_reference varchar(255) NOT NULL,
      source_revision varchar(255) NOT NULL,
      observed_at timestamptz NOT NULL,
      normalizer_version varchar(64) NOT NULL,
      canonical_payload text NOT NULL,
      evidence_sha256 bytea NOT NULL,
      supersedes_usage_event_id uuid,
      recorded_at timestamptz NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT pk_usage_events PRIMARY KEY (usage_event_id),
      CONSTRAINT uq_usage_events_source_identity UNIQUE (execution_id,normalizer_version,source_revision),
      CONSTRAINT uq_usage_events_single_successor UNIQUE (supersedes_usage_event_id),
      CONSTRAINT uq_usage_events_binding UNIQUE
        (usage_event_id,execution_id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id),
      CONSTRAINT fk_usage_events_task_binding FOREIGN KEY
        (task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        REFERENCES public.tasks(id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_usage_events_execution FOREIGN KEY (execution_id)
        REFERENCES public.executions(id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_usage_events_route_decision FOREIGN KEY (route_decision_id)
        REFERENCES public.route_decisions(task_id) ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT fk_usage_events_supersession_binding FOREIGN KEY
        (supersedes_usage_event_id,execution_id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        REFERENCES public.usage_events
        (usage_event_id,execution_id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE,
      CONSTRAINT ck_usage_events_decision_binding CHECK
        (route_decision_id IS NULL OR route_decision_id=task_id),
      CONSTRAINT ck_usage_events_route_versions CHECK
        ((route_decision_id IS NULL AND logical_model_version IS NULL AND route_version IS NULL) OR
         (route_decision_id IS NOT NULL AND logical_model_version>0 AND route_version>0)),
      CONSTRAINT ck_usage_events_status CHECK (usage_status IN ('AVAILABLE','PARTIAL','UNAVAILABLE')),
      CONSTRAINT ck_usage_events_source CHECK
        (source_type='execution_usage' AND source_reference=execution_id::text AND source_revision='execution-row-v1'),
      CONSTRAINT ck_usage_events_digest_bounds CHECK
        (octet_length(evidence_sha256)=32 AND octet_length(canonical_payload) BETWEEN 1 AND 32768),
      CONSTRAINT ck_usage_events_digest CHECK
        (evidence_sha256=pg_catalog.sha256(pg_catalog.convert_to(canonical_payload,'UTF8'))),
      CONSTRAINT ck_usage_events_canonical_binding CHECK
        (canonical_payload::jsonb=pg_catalog.jsonb_build_object(
          'schema_version','jous.usage-event.v1','usage_event_id',usage_event_id,
          'organization_id',organization_id,'project_id',project_id,'actor_user_id',actor_user_id,
          'task_id',task_id,'dispatch_claim_id',dispatch_claim_id,'execution_id',execution_id,
          'route_decision_id',route_decision_id,'logical_model_id',logical_model_id,
          'logical_model_version',logical_model_version,'route_id',route_id,'route_version',route_version,
          'supplier_id',supplier_id,'underlying_provider',underlying_provider,
          'reported_provider_id',reported_provider_id,'input_tokens',input_tokens,
          'output_tokens',output_tokens,'total_tokens',total_tokens,
          'cached_input_tokens',cached_input_tokens,'reasoning_tokens',reasoning_tokens,
          'usage_status',usage_status,'source_type',source_type,'source_reference',source_reference,
          'source_revision',source_revision,
          'observed_at',pg_catalog.to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
          'normalizer_version',normalizer_version,'supersedes_usage_event_id',supersedes_usage_event_id)),
      CONSTRAINT ck_usage_events_status_values CHECK
        ((usage_status='UNAVAILABLE' AND input_tokens IS NULL AND output_tokens IS NULL AND total_tokens IS NULL
          AND cached_input_tokens IS NULL AND reasoning_tokens IS NULL) OR
         (usage_status='PARTIAL' AND num_nonnulls(input_tokens,output_tokens,total_tokens,cached_input_tokens,reasoning_tokens)>0) OR
         (usage_status='AVAILABLE' AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL AND total_tokens IS NOT NULL)),
      CONSTRAINT ck_usage_events_nonnegative CHECK
        ((input_tokens IS NULL OR input_tokens>=0) AND (output_tokens IS NULL OR output_tokens>=0) AND
         (total_tokens IS NULL OR total_tokens>=0) AND (cached_input_tokens IS NULL OR cached_input_tokens>=0) AND
         (reasoning_tokens IS NULL OR reasoning_tokens>=0)),
      CONSTRAINT ck_usage_events_identity CHECK
        (length(btrim(logical_model_id))>0 AND length(btrim(supplier_id))>0 AND
         length(btrim(underlying_provider))>0 AND length(btrim(normalizer_version))>0 AND
         length(btrim(source_revision))>0 AND pg_catalog.isfinite(observed_at) AND pg_catalog.isfinite(recorded_at))
    )""",
    "CREATE INDEX ix_usage_events_project_recorded ON public.usage_events(organization_id,project_id,recorded_at,usage_event_id)",
    "ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.usage_events FORCE ROW LEVEL SECURITY",
    "REVOKE ALL PRIVILEGES ON TABLE public.usage_events FROM PUBLIC,jous_runtime,jous_security_reader",
    "CREATE POLICY jous_usage_events_select ON public.usage_events AS PERMISSIVE FOR SELECT TO jous_runtime USING (EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=usage_events.task_id AND t.organization_id=usage_events.organization_id AND t.project_id=usage_events.project_id AND t.actor_user_id=usage_events.actor_user_id AND t.dispatch_claim_id=usage_events.dispatch_claim_id) AND EXISTS (SELECT 1 FROM public.executions e WHERE e.id=usage_events.execution_id AND e.task_id=usage_events.task_id AND e.organization_id=usage_events.organization_id AND e.project_id=usage_events.project_id AND e.actor_user_id=usage_events.actor_user_id AND e.dispatch_claim_id=usage_events.dispatch_claim_id))",
    "CREATE POLICY jous_usage_events_insert ON public.usage_events AS PERMISSIVE FOR INSERT TO jous_runtime WITH CHECK (actor_user_id=(CASE WHEN pg_catalog.length(pg_catalog.current_setting('jous.user_id',true))=36 AND pg_catalog.current_setting('jous.user_id',true) OPERATOR(pg_catalog.~) '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN CAST(pg_catalog.current_setting('jous.user_id',true) AS pg_catalog.uuid) ELSE NULL END) AND EXISTS (SELECT 1 FROM public.tasks t WHERE t.id=usage_events.task_id AND t.organization_id=usage_events.organization_id AND t.project_id=usage_events.project_id AND t.actor_user_id=usage_events.actor_user_id AND t.dispatch_claim_id=usage_events.dispatch_claim_id AND EXISTS (SELECT 1 FROM public.organization_memberships m WHERE m.organization_id=t.organization_id AND m.user_id=(CASE WHEN pg_catalog.length(pg_catalog.current_setting('jous.user_id',true))=36 AND pg_catalog.current_setting('jous.user_id',true) OPERATOR(pg_catalog.~) '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN CAST(pg_catalog.current_setting('jous.user_id',true) AS pg_catalog.uuid) ELSE NULL END) AND m.status='active' AND m.role='owner')) AND EXISTS (SELECT 1 FROM public.executions e WHERE e.id=usage_events.execution_id AND e.task_id=usage_events.task_id AND e.organization_id=usage_events.organization_id AND e.project_id=usage_events.project_id AND e.actor_user_id=usage_events.actor_user_id AND e.dispatch_claim_id=usage_events.dispatch_claim_id AND ((e.usage_status='unavailable' AND e.usage IS NULL AND usage_events.usage_status='UNAVAILABLE') OR (e.usage_status IN ('available','partial') AND e.usage IS NOT NULL AND usage_events.usage_status=pg_catalog.upper(e.usage_status) AND e.usage=pg_catalog.jsonb_strip_nulls(pg_catalog.jsonb_build_object('input_tokens',usage_events.input_tokens,'output_tokens',usage_events.output_tokens,'total_tokens',usage_events.total_tokens,'cached_input_tokens',usage_events.cached_input_tokens,'reasoning_tokens',usage_events.reasoning_tokens)))) AND ((usage_events.route_decision_id IS NULL AND NOT EXISTS (SELECT 1 FROM public.route_decisions d WHERE d.task_id=usage_events.task_id)) OR (usage_events.route_decision_id=usage_events.task_id AND EXISTS (SELECT 1 FROM public.route_decisions d WHERE d.task_id=usage_events.task_id AND d.organization_id=usage_events.organization_id AND d.project_id=usage_events.project_id AND d.actor_user_id=usage_events.actor_user_id AND d.dispatch_claim_id=usage_events.dispatch_claim_id AND d.logical_model_id=usage_events.logical_model_id AND d.logical_model_version=usage_events.logical_model_version AND d.selected_route_id=usage_events.route_id AND d.selected_route_version=usage_events.route_version)))))",
    "GRANT SELECT (usage_event_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,execution_id,route_decision_id,logical_model_id,logical_model_version,route_id,route_version,supplier_id,underlying_provider,reported_provider_id,input_tokens,output_tokens,total_tokens,cached_input_tokens,reasoning_tokens,usage_status,source_type,source_reference,source_revision,observed_at,normalizer_version,canonical_payload,evidence_sha256,supersedes_usage_event_id,recorded_at) ON public.usage_events TO jous_runtime",
    "GRANT INSERT (usage_event_id,organization_id,project_id,actor_user_id,task_id,dispatch_claim_id,execution_id,route_decision_id,logical_model_id,logical_model_version,route_id,route_version,supplier_id,underlying_provider,reported_provider_id,input_tokens,output_tokens,total_tokens,cached_input_tokens,reasoning_tokens,usage_status,source_type,source_reference,source_revision,observed_at,normalizer_version,canonical_payload,evidence_sha256,supersedes_usage_event_id) ON public.usage_events TO jous_runtime",
)


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError("V1.4 UsageEvents are append-only; forward migration required")
