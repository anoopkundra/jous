"""Source-owned V1.4B UsageEvent relation; import registers metadata only."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.sql.elements import conv

from .models import Base


usage_events = sa.Table(
    "usage_events", Base.metadata,
    sa.Column("usage_event_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("project_id", UUID(as_uuid=True), nullable=False),
    sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
    sa.Column("task_id", UUID(as_uuid=True), nullable=False),
    sa.Column("dispatch_claim_id", UUID(as_uuid=True), nullable=False),
    sa.Column("execution_id", UUID(as_uuid=True), nullable=False),
    sa.Column("route_decision_id", UUID(as_uuid=True), nullable=True),
    sa.Column("logical_model_id", sa.String(255), nullable=False),
    sa.Column("logical_model_version", sa.Integer(), nullable=True),
    sa.Column("route_id", sa.String(255), nullable=True),
    sa.Column("route_version", sa.Integer(), nullable=True),
    sa.Column("supplier_id", sa.String(255), nullable=False),
    sa.Column("underlying_provider", sa.String(255), nullable=False),
    sa.Column("reported_provider_id", sa.String(255), nullable=True),
    sa.Column("input_tokens", sa.BigInteger(), nullable=True),
    sa.Column("output_tokens", sa.BigInteger(), nullable=True),
    sa.Column("total_tokens", sa.BigInteger(), nullable=True),
    sa.Column("cached_input_tokens", sa.BigInteger(), nullable=True),
    sa.Column("reasoning_tokens", sa.BigInteger(), nullable=True),
    sa.Column("usage_status", sa.String(16), nullable=False),
    sa.Column("source_type", sa.String(32), nullable=False),
    sa.Column("source_reference", sa.String(255), nullable=False),
    sa.Column("source_revision", sa.String(255), nullable=False),
    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("normalizer_version", sa.String(64), nullable=False),
    sa.Column("canonical_payload", sa.Text(), nullable=False),
    sa.Column("evidence_sha256", BYTEA(), nullable=False),
    sa.Column("supersedes_usage_event_id", UUID(as_uuid=True), nullable=True),
    sa.Column("recorded_at", sa.DateTime(timezone=True),
              server_default=sa.text("statement_timestamp()"), nullable=False),
    sa.PrimaryKeyConstraint("usage_event_id", name="pk_usage_events"),
    sa.UniqueConstraint("execution_id", "normalizer_version", "source_revision",
                        name="uq_usage_events_source_identity"),
    sa.UniqueConstraint("supersedes_usage_event_id", name="uq_usage_events_single_successor"),
    sa.UniqueConstraint("usage_event_id", "execution_id", "task_id", "organization_id",
                        "project_id", "actor_user_id", "dispatch_claim_id",
                        name="uq_usage_events_binding"),
    sa.ForeignKeyConstraint(
        ["task_id", "organization_id", "project_id", "actor_user_id", "dispatch_claim_id"],
        ["public.tasks.id", "public.tasks.organization_id", "public.tasks.project_id",
         "public.tasks.actor_user_id", "public.tasks.dispatch_claim_id"],
        name="fk_usage_events_task_binding", ondelete="RESTRICT", onupdate="RESTRICT",
        deferrable=False, initially="IMMEDIATE"),
    sa.ForeignKeyConstraint(
        ["execution_id"], ["public.executions.id"], name="fk_usage_events_execution",
        ondelete="RESTRICT", onupdate="RESTRICT", deferrable=False, initially="IMMEDIATE"),
    sa.ForeignKeyConstraint(
        ["route_decision_id"], ["public.route_decisions.task_id"],
        name="fk_usage_events_route_decision", ondelete="RESTRICT", onupdate="RESTRICT",
        deferrable=False, initially="IMMEDIATE"),
    sa.ForeignKeyConstraint(
        ["supersedes_usage_event_id", "execution_id", "task_id", "organization_id",
         "project_id", "actor_user_id", "dispatch_claim_id"],
        ["public.usage_events.usage_event_id", "public.usage_events.execution_id",
         "public.usage_events.task_id", "public.usage_events.organization_id",
         "public.usage_events.project_id", "public.usage_events.actor_user_id",
         "public.usage_events.dispatch_claim_id"],
        name="fk_usage_events_supersession_binding", ondelete="RESTRICT", onupdate="RESTRICT",
        deferrable=False, initially="IMMEDIATE"),
    sa.CheckConstraint("route_decision_id IS NULL OR route_decision_id = task_id",
                       name=conv("ck_usage_events_decision_binding")),
    sa.CheckConstraint("usage_status IN ('AVAILABLE','PARTIAL','UNAVAILABLE')",
                       name=conv("ck_usage_events_status")),
    sa.CheckConstraint("source_type = 'execution_usage' AND source_reference = execution_id::text AND source_revision = 'execution-row-v1'",
                       name=conv("ck_usage_events_source")),
    sa.CheckConstraint("octet_length(evidence_sha256) = 32 AND octet_length(canonical_payload) BETWEEN 1 AND 32768",
                       name=conv("ck_usage_events_digest_bounds")),
    sa.CheckConstraint("evidence_sha256 = pg_catalog.sha256(pg_catalog.convert_to(canonical_payload, 'UTF8'))",
                       name=conv("ck_usage_events_digest")),
    sa.CheckConstraint("canonical_payload::jsonb = pg_catalog.jsonb_build_object("
        "'schema_version','jous.usage-event.v1','usage_event_id',usage_event_id,'organization_id',organization_id,"
        "'project_id',project_id,'actor_user_id',actor_user_id,'task_id',task_id,'dispatch_claim_id',dispatch_claim_id,"
        "'execution_id',execution_id,'route_decision_id',route_decision_id,'logical_model_id',logical_model_id,"
        "'logical_model_version',logical_model_version,'route_id',route_id,'route_version',route_version,"
        "'supplier_id',supplier_id,'underlying_provider',underlying_provider,'reported_provider_id',reported_provider_id,"
        "'input_tokens',input_tokens,'output_tokens',output_tokens,'total_tokens',total_tokens,"
        "'cached_input_tokens',cached_input_tokens,'reasoning_tokens',reasoning_tokens,'usage_status',usage_status,"
        "'source_type',source_type,'source_reference',source_reference,'source_revision',source_revision,"
        "'observed_at',pg_catalog.to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'),"
        "'normalizer_version',normalizer_version,'supersedes_usage_event_id',supersedes_usage_event_id)",
        name=conv("ck_usage_events_canonical_binding")),
    sa.CheckConstraint(
        "(usage_status = 'UNAVAILABLE' AND input_tokens IS NULL AND output_tokens IS NULL AND total_tokens IS NULL AND cached_input_tokens IS NULL AND reasoning_tokens IS NULL) OR "
        "(usage_status = 'PARTIAL' AND num_nonnulls(input_tokens,output_tokens,total_tokens,cached_input_tokens,reasoning_tokens) > 0) OR "
        "(usage_status = 'AVAILABLE' AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL AND total_tokens IS NOT NULL)",
        name=conv("ck_usage_events_status_values")),
    sa.CheckConstraint("num_nonnulls(input_tokens,output_tokens,total_tokens,cached_input_tokens,reasoning_tokens) = 0 OR "
                       "least(coalesce(input_tokens,0),coalesce(output_tokens,0),coalesce(total_tokens,0),coalesce(cached_input_tokens,0),coalesce(reasoning_tokens,0)) >= 0",
                       name=conv("ck_usage_events_nonnegative")),
    sa.CheckConstraint("(route_decision_id IS NULL AND logical_model_version IS NULL AND route_version IS NULL) OR "
                       "(route_decision_id IS NOT NULL AND logical_model_version > 0 AND route_version > 0)",
                       name=conv("ck_usage_events_route_versions")),
    sa.CheckConstraint("length(btrim(logical_model_id)) > 0 AND length(btrim(supplier_id)) > 0 AND "
                       "length(btrim(underlying_provider)) > 0 AND length(btrim(normalizer_version)) > 0 AND "
                       "length(btrim(source_revision)) > 0 AND pg_catalog.isfinite(observed_at) AND pg_catalog.isfinite(recorded_at)",
                       name=conv("ck_usage_events_identity")),
)
sa.Index("ix_usage_events_project_recorded", usage_events.c.organization_id,
         usage_events.c.project_id, usage_events.c.recorded_at, usage_events.c.usage_event_id)
