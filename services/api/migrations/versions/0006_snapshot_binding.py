"""Require every route-decision snapshot binding to evaluate TRUE."""

from alembic import op


revision = "0006_snapshot_binding"
down_revision = "0005_route_economics"
branch_labels = None
depends_on = None


SNAPSHOT_BINDING_PREDICATE = """(
    (decision_snapshot::jsonb->>'decision_version')=decision_version AND
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
    decision_snapshot::jsonb->'selected'->>'currency'=currency
) IS TRUE"""
UPGRADE_SQL = f"""ALTER TABLE public.route_decisions
    DROP CONSTRAINT ck_route_decisions_snapshot_binding,
    ADD CONSTRAINT ck_route_decisions_snapshot_binding
    CHECK ({SNAPSHOT_BINDING_PREDICATE})"""


def upgrade():
    # One ALTER TABLE statement is transactional: if validation finds a legacy
    # row that does not satisfy the true-only predicate, PostgreSQL restores
    # the 0005 constraint and Alembic keeps the 0005 revision.
    op.execute(UPGRADE_SQL)


def downgrade():
    # Keep this hardening monotonic if the revision marker is moved backward.
    pass
