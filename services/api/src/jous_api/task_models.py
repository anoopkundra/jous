"""V1.2 source-owned append-only schema contract. No connection or DDL on import."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, BYTEA, JSONB
from sqlalchemy.sql.elements import conv
from .models import Base

TASK_COLUMNS = ('id','organization_id','project_id','actor_user_id','client_request_id','request_sha256',
    'prompt','context_package','context_sha256','logical_model_id','supplier_id','supplier_native_model_id',
    'underlying_provider','admission_version','request_parameters','tokenizer_manifest_sha256','template_branch',
    'token_bound_method','token_bound_evidence','input_token_upper_bound','output_allowance','safety_margin',
    'dispatch_claim_id','dispatch_deadline_at','created_at')
EXECUTION_COLUMNS = ('id','task_id','organization_id','project_id','actor_user_id','dispatch_claim_id','status',
    'response_text','reported_model_id','reported_provider_id','provider_request_id','provider_response_id',
    'finish_reason','usage','usage_status','error_code','request_started_at','response_received_at',
    'credential_authority_ref','recorded_at')
TASK_SELECT_COLUMNS = TASK_COLUMNS
TASK_INSERT_COLUMNS = TASK_COLUMNS[:-1]
EXECUTION_SELECT_COLUMNS = EXECUTION_COLUMNS
EXECUTION_INSERT_COLUMNS = EXECUTION_COLUMNS[:-1]
TASK_IDENTIFIERS = ('logical_model_id','supplier_id','supplier_native_model_id','underlying_provider',
                    'admission_version','template_branch','token_bound_method')
EXECUTION_IDENTIFIERS = ('reported_model_id','reported_provider_id','provider_request_id','provider_response_id',
                         'finish_reason')


def required_identifier(name):
    return f"length(btrim({name})) > 0 AND octet_length({name}) <= 255"


TASK_CHECKS = {
 'ck_tasks_hash_lengths': ' AND '.join(f'octet_length({c}) = 32' for c in ('request_sha256','context_sha256','tokenizer_manifest_sha256')),
 'ck_tasks_prompt_bounds': 'length(btrim(prompt)) > 0 AND octet_length(prompt) <= 8192',
 'ck_tasks_identifier_bounds': ' AND '.join(required_identifier(c) for c in TASK_IDENTIFIERS),
 'ck_tasks_json_shapes': " AND ".join(
     f"jsonb_typeof({c}) = 'object' AND {c} ? 'schema_version' AND {c}->'schema_version' = '1'::jsonb"
     for c in ('context_package','request_parameters','token_bound_evidence')) +
     " AND context_package ?& ARRAY['snapshot','instruction','provenance']"
     " AND jsonb_typeof(context_package->'snapshot') = 'object'"
     " AND jsonb_typeof(context_package->'instruction') = 'object'"
     " AND jsonb_typeof(context_package->'provenance') = 'object'"
     " AND request_parameters ?& ARRAY['route_id','catalog_digest','route_snapshot','limits','execution']"
     " AND jsonb_typeof(request_parameters->'route_id') = 'string'"
     " AND jsonb_typeof(request_parameters->'catalog_digest') = 'string'"
     " AND jsonb_typeof(request_parameters->'route_snapshot') = 'object'"
     " AND jsonb_typeof(request_parameters->'limits') = 'object'"
     " AND jsonb_typeof(request_parameters->'execution') = 'object'"
     " AND token_bound_evidence ?& ARRAY['asset_revision','asset_hashes','method','template_branch','input_token_upper_bound','context_capacity','output_allowance','safety_margin','hosted_authority_state']"
     " AND jsonb_typeof(token_bound_evidence->'asset_hashes') = 'object'"
     " AND jsonb_typeof(token_bound_evidence->'context_capacity') = 'number'"
     " AND jsonb_typeof(token_bound_evidence->'method') = 'string'"
     " AND jsonb_typeof(token_bound_evidence->'hosted_authority_state') = 'string'",
 'ck_tasks_json_bounds': ' AND '.join(f'octet_length({c}::text) <= 131072' for c in ('context_package','request_parameters','token_bound_evidence')),
 'ck_tasks_token_bounds': 'input_token_upper_bound BETWEEN 0 AND 28467 AND output_allowance = 1024 AND safety_margin = 3277 AND input_token_upper_bound + output_allowance + safety_margin <= 32768',
 'ck_tasks_deadline_order': "isfinite(created_at) AND isfinite(dispatch_deadline_at) AND dispatch_deadline_at > created_at AND dispatch_deadline_at <= created_at + interval '40 seconds'",
}
EXECUTION_CHECKS = {
 'ck_executions_status': "status IN ('succeeded','refused','known_error','unknown')",
 'ck_executions_response_bounds': 'response_text IS NULL OR octet_length(response_text) <= 65536',
 'ck_executions_identifier_bounds': ' AND '.join(f'({c} IS NULL OR ({required_identifier(c)}))' for c in EXECUTION_IDENTIFIERS),
 'ck_executions_usage_shape': "usage IS NULL OR (jsonb_typeof(usage) = 'object' AND usage <> '{}'::jsonb)",
 'ck_executions_usage_bounds': 'usage IS NULL OR octet_length(usage::text) <= 32768',
 'ck_executions_usage_status': "(usage_status = 'unavailable' AND usage IS NULL) OR (usage_status IN ('available','partial') AND usage IS NOT NULL AND usage <> '{}'::jsonb)",
 'ck_executions_error_code': "error_code IS NULL OR error_code IN ('not_dispatched','supplier_rejected','rate_limited','malformed_response','response_too_large','metadata_inconsistent','transport_ambiguous','provider_timeout')",
 'ck_executions_outcome_shape': "((status = 'succeeded' AND response_text IS NOT NULL AND error_code IS NULL) OR "
     "(status = 'refused' AND error_code IS NULL) OR "
     "(status = 'known_error' AND error_code IS NOT NULL AND error_code IN ('not_dispatched','supplier_rejected','rate_limited','malformed_response','response_too_large','metadata_inconsistent') AND response_text IS NULL) OR "
     "(status = 'unknown' AND error_code IS NOT NULL AND error_code IN ('transport_ambiguous','provider_timeout') AND response_text IS NULL)) AND "
     "(error_code IS DISTINCT FROM 'not_dispatched' OR (request_started_at IS NULL AND response_received_at IS NULL AND reported_model_id IS NULL AND reported_provider_id IS NULL AND provider_request_id IS NULL AND provider_response_id IS NULL AND finish_reason IS NULL AND usage IS NULL AND usage_status = 'unavailable'))",
 'ck_executions_timestamp_order': 'isfinite(recorded_at) AND (request_started_at IS NULL OR (isfinite(request_started_at) AND recorded_at >= request_started_at)) AND '
     '(response_received_at IS NULL OR (isfinite(response_received_at) AND request_started_at IS NOT NULL AND response_received_at >= request_started_at AND recorded_at >= response_received_at))',
 'ck_executions_credential_authority_ref': 'credential_authority_ref IS NULL OR (length(btrim(credential_authority_ref)) > 0 AND octet_length(credential_authority_ref) <= 255)',
}


def table_columns(names, uuid_names, hashes=(), json_names=(), integers=(), timestamps=(), nullable=(), default=None):
    for name in names:
        typ = (UUID(as_uuid=True) if name in uuid_names else BYTEA() if name in hashes else JSONB()
               if name in json_names else sa.Integer() if name in integers else sa.DateTime(timezone=True)
               if name in timestamps else sa.String(255) if name == 'credential_authority_ref' else sa.Text())
        yield sa.Column(name, typ, nullable=name in nullable,
                        server_default=sa.text('statement_timestamp()') if name == default else None)


tasks = sa.Table('tasks', Base.metadata,
    *table_columns(TASK_COLUMNS, ('id','organization_id','project_id','actor_user_id','client_request_id','dispatch_claim_id'),
        ('request_sha256','context_sha256','tokenizer_manifest_sha256'), ('context_package','request_parameters','token_bound_evidence'),
        ('input_token_upper_bound','output_allowance','safety_margin'), ('dispatch_deadline_at','created_at'), default='created_at'),
    sa.PrimaryKeyConstraint('id', name='pk_tasks'),
    sa.UniqueConstraint('organization_id','project_id','actor_user_id','client_request_id',name='uq_tasks_request'),
    sa.UniqueConstraint('dispatch_claim_id',name='uq_tasks_dispatch_claim_id'),
    sa.UniqueConstraint('id','organization_id','project_id','actor_user_id','dispatch_claim_id',name='uq_tasks_execution_binding'),
    sa.ForeignKeyConstraint(['organization_id','project_id'],['public.projects.organization_id','public.projects.id'],
        name='fk_tasks_project_binding', ondelete='RESTRICT', onupdate='RESTRICT', deferrable=False, initially='IMMEDIATE'),
    sa.ForeignKeyConstraint(['actor_user_id'],['public.users.id'],name='fk_tasks_actor_user',
        ondelete='RESTRICT', onupdate='RESTRICT', deferrable=False, initially='IMMEDIATE'),
    *(sa.CheckConstraint(sql, name=conv(name)) for name,sql in TASK_CHECKS.items()))
sa.Index('ix_tasks_project_created_id',tasks.c.organization_id,tasks.c.project_id,tasks.c.created_at,tasks.c.id)
executions = sa.Table('executions', Base.metadata,
    *table_columns(EXECUTION_COLUMNS, ('id','task_id','organization_id','project_id','actor_user_id','dispatch_claim_id'),
        json_names=('usage',), timestamps=('request_started_at','response_received_at','recorded_at'),
        nullable=('response_text',*EXECUTION_IDENTIFIERS,'usage','error_code','request_started_at','response_received_at',
                  'credential_authority_ref'), default='recorded_at'),
    sa.PrimaryKeyConstraint('id', name='pk_executions'),
    sa.UniqueConstraint('task_id',name='uq_executions_task_id'),
    sa.UniqueConstraint('dispatch_claim_id',name='uq_executions_dispatch_claim_id'),
    sa.ForeignKeyConstraint(['task_id','organization_id','project_id','actor_user_id','dispatch_claim_id'],
        ['public.tasks.'+c for c in ('id','organization_id','project_id','actor_user_id','dispatch_claim_id')],
        name='fk_executions_task_binding', ondelete='RESTRICT', onupdate='RESTRICT', deferrable=False, initially='IMMEDIATE'),
    *(sa.CheckConstraint(sql, name=conv(name)) for name,sql in EXECUTION_CHECKS.items()))


class Task(Base):
    __table__ = tasks


class Execution(Base):
    __table__ = executions


def context_uuid(name):
    value = f"pg_catalog.current_setting('jous.{name}', true)"
    return (f"(CASE WHEN pg_catalog.length({value}) = 36 AND {value} OPERATOR(pg_catalog.~) "
            "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "
            f"THEN CAST({value} AS pg_catalog.uuid) ELSE NULL END)")


U, O = context_uuid('user_id'), context_uuid('organization_id')


def owner(org):
    return f"EXISTS (SELECT 1 FROM public.organization_memberships m WHERE m.organization_id = {org} AND m.user_id = {U} AND m.status = 'active' AND m.role = 'owner')"


def access(org, project):
    return (f"{org} = {O} AND jous_security.organization_is_active({org}) AND "
        f"EXISTS (SELECT 1 FROM public.users u WHERE u.id = {U} AND u.status = 'active') AND "
        f"EXISTS (SELECT 1 FROM public.organization_memberships m WHERE m.organization_id = {org} AND m.user_id = {U} AND m.status = 'active' AND m.role IN ('owner','member')) AND "
        f"EXISTS (SELECT 1 FROM public.projects p WHERE p.organization_id = {org} AND p.id = {project} AND p.status = 'active')")


BINDING = ' AND '.join(f'executions.{e} = t.{t}' for e,t in
    [('task_id','id'),('organization_id','organization_id'),('project_id','project_id'),('actor_user_id','actor_user_id'),('dispatch_claim_id','dispatch_claim_id')])
POLICIES = {
 'jous_tasks_select': ('tasks','SELECT',access('tasks.organization_id','tasks.project_id')),
 'jous_tasks_insert': ('tasks','INSERT',access('tasks.organization_id','tasks.project_id') + f' AND {owner("tasks.organization_id")} AND tasks.actor_user_id = {U}'),
 'jous_executions_select': ('executions','SELECT',f'EXISTS (SELECT 1 FROM public.tasks t WHERE {BINDING})'),
 'jous_executions_insert': ('executions','INSERT',f'executions.actor_user_id = {U} AND EXISTS (SELECT 1 FROM public.tasks t WHERE {BINDING} AND {owner("t.organization_id")} AND '
     '(executions.request_started_at IS NULL OR (executions.request_started_at >= t.created_at AND executions.request_started_at < t.dispatch_deadline_at)) AND '
     '(executions.response_received_at IS NULL OR executions.response_received_at >= t.created_at))'),
}
