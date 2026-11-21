"""V1.4C immutable receipt and append-only ledger schema representations."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, BYTEA, CHAR
from sqlalchemy.sql.elements import conv

from .models import Base


supplier_funding_authorities = sa.Table(
    "supplier_funding_authorities", Base.metadata,
    sa.Column("funding_authority_id", UUID(as_uuid=True), nullable=False),
    sa.Column("authority_version", sa.Integer(), nullable=False),
    sa.Column("scope", sa.String(24), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
    sa.Column("supplier_id", sa.String(255), nullable=False),
    sa.Column("route_id", sa.String(255), nullable=False),
    sa.Column("route_version", sa.Integer(), nullable=False),
    sa.Column("credential_authority_ref", sa.String(255), nullable=True),
    sa.Column("account_owner", sa.String(16), nullable=False),
    sa.Column("cost_bearer", sa.String(24), nullable=False),
    sa.Column("evidence_type", sa.String(32), nullable=False),
    sa.Column("evidence_reference", sa.String(255), nullable=False),
    sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("canonical_evidence", sa.Text(), nullable=False),
    sa.Column("authority_digest", BYTEA(), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True),
              server_default=sa.text("statement_timestamp()"), nullable=False),
    sa.PrimaryKeyConstraint("funding_authority_id", "authority_version",
                            name="pk_supplier_funding_authorities"),
    sa.ForeignKeyConstraint(["organization_id"], ["public.organizations.id"],
                            name="fk_supplier_funding_authorities_organization",
                            ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.UniqueConstraint("funding_authority_id", "authority_version", "authority_digest",
                        name="uq_supplier_funding_authorities_digest_binding"),
    sa.CheckConstraint("authority_version>0 AND route_version>0", name=conv("ck_supplier_funding_authorities_versions")),
    sa.CheckConstraint("scope IN ('JOUS_GLOBAL','ORGANIZATION')", name=conv("ck_supplier_funding_authorities_scope")),
    sa.CheckConstraint("(scope='JOUS_GLOBAL' AND organization_id IS NULL) OR "
                       "(scope='ORGANIZATION' AND organization_id IS NOT NULL)",
                       name=conv("ck_supplier_funding_authorities_scope_binding")),
    sa.CheckConstraint("account_owner IN ('JOUS','CUSTOMER','OTHER','UNKNOWN')",
                       name=conv("ck_supplier_funding_authorities_owner")),
    sa.CheckConstraint("cost_bearer IN ('JOUS_BORNE','CUSTOMER_DIRECT','UNKNOWN')",
                       name=conv("ck_supplier_funding_authorities_bearer")),
    sa.CheckConstraint("cost_bearer<>'CUSTOMER_DIRECT' OR "
                       "(scope='ORGANIZATION' AND account_owner='CUSTOMER')",
                       name=conv("ck_supplier_funding_authorities_direct_customer")),
    sa.CheckConstraint("octet_length(authority_digest)=32 AND "
                       "length(btrim(supplier_id))>0 AND length(btrim(route_id))>0 AND "
                       "length(btrim(evidence_type))>0 AND length(btrim(evidence_reference))>0 AND "
                       "(credential_authority_ref IS NULL OR length(btrim(credential_authority_ref))>0) AND "
                       "pg_catalog.isfinite(effective_at) AND pg_catalog.isfinite(recorded_at) AND "
                       "canonical_evidence=pg_catalog.jsonb_build_object(" 
                       "'schema_version','jous.supplier-funding-authority.v1','funding_authority_id',funding_authority_id," 
                       "'authority_version',authority_version,'scope',scope,'organization_id',organization_id," 
                       "'supplier_id',supplier_id,'route_id',route_id,'route_version',route_version," 
                       "'credential_authority_ref',credential_authority_ref,'account_owner',account_owner," 
                       "'cost_bearer',cost_bearer,'evidence_type',evidence_type,'evidence_reference',evidence_reference," 
                       "'effective_at',pg_catalog.to_char(effective_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'))::text AND " 
                       "authority_digest=pg_catalog.sha256(pg_catalog.convert_to(canonical_evidence,'UTF8'))",
                       name=conv("ck_supplier_funding_authorities_evidence")),
)
sa.Index("ix_supplier_funding_authorities_org_route", supplier_funding_authorities.c.organization_id,
         supplier_funding_authorities.c.route_id, supplier_funding_authorities.c.route_version,
         supplier_funding_authorities.c.authority_version)


economic_receipts = sa.Table(
    "economic_receipts", Base.metadata,
    sa.Column("economic_receipt_id", UUID(as_uuid=True), nullable=False),
    sa.Column("assessment_key", BYTEA(), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("project_id", UUID(as_uuid=True), nullable=False),
    sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
    sa.Column("task_id", UUID(as_uuid=True), nullable=False),
    sa.Column("dispatch_claim_id", UUID(as_uuid=True), nullable=False),
    sa.Column("execution_id", UUID(as_uuid=True), nullable=False),
    sa.Column("usage_event_id", UUID(as_uuid=True), nullable=False),
    sa.Column("route_decision_id", UUID(as_uuid=True), nullable=True),
    sa.Column("pricing_version_id", sa.String(255), nullable=True),
    sa.Column("funding_authority_id", UUID(as_uuid=True), nullable=True),
    sa.Column("funding_authority_version", sa.Integer(), nullable=True),
    sa.Column("funding_authority_digest", BYTEA(), nullable=True),
    sa.Column("economic_policy_version", sa.Text(), nullable=False),
    sa.Column("treatment_policy_digest", BYTEA(), nullable=False),
    sa.Column("calculation_version", sa.Text(), nullable=False),
    sa.Column("assessment_status", sa.String(24), nullable=False),
    sa.Column("cost_bearer", sa.String(24), nullable=False),
    sa.Column("currency", CHAR(3), nullable=False),
    sa.Column("provider_usage_cost_usd", sa.Numeric(50, 18), nullable=True),
    sa.Column("provider_request_fee_usd", sa.Numeric(50, 18), nullable=True),
    sa.Column("gateway_request_fee_usd", sa.Numeric(50, 18), nullable=True),
    sa.Column("computed_usage_cost_usd", sa.Numeric(50, 18), nullable=True),
    sa.Column("pricing_snapshot_canonical", sa.Text(), nullable=True),
    sa.Column("pricing_snapshot_sha256", BYTEA(), nullable=True),
    sa.Column("source_usage_digest", BYTEA(), nullable=False),
    sa.Column("canonical_digest", BYTEA(), nullable=False),
    sa.Column("supersedes_receipt_id", UUID(as_uuid=True), nullable=True),
    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True),
              server_default=sa.text("statement_timestamp()"), nullable=False),
    sa.PrimaryKeyConstraint("economic_receipt_id", name="pk_economic_receipts"),
    sa.UniqueConstraint("assessment_key", name="uq_economic_receipts_assessment_key"),
    sa.UniqueConstraint("supersedes_receipt_id", name="uq_economic_receipts_single_successor"),
    sa.UniqueConstraint("economic_receipt_id", "organization_id", "canonical_digest",
                        name="uq_economic_receipts_ledger_binding"),
    sa.UniqueConstraint("economic_receipt_id", "usage_event_id", "execution_id", "task_id",
                        "organization_id", "project_id", "actor_user_id", "dispatch_claim_id",
                        name="uq_economic_receipts_source_binding"),
    sa.ForeignKeyConstraint(
        ["usage_event_id", "execution_id", "task_id", "organization_id", "project_id",
         "actor_user_id", "dispatch_claim_id"],
        ["public.usage_events.usage_event_id", "public.usage_events.execution_id",
         "public.usage_events.task_id", "public.usage_events.organization_id",
         "public.usage_events.project_id", "public.usage_events.actor_user_id",
         "public.usage_events.dispatch_claim_id"],
        name="fk_economic_receipts_usage_binding", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.ForeignKeyConstraint(["route_decision_id"], ["public.route_decisions.task_id"],
        name="fk_economic_receipts_route_decision", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.ForeignKeyConstraint(["pricing_version_id"], ["public.route_pricing_versions.pricing_version_id"],
        name="fk_economic_receipts_pricing_version", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.ForeignKeyConstraint(["funding_authority_id", "funding_authority_version", "funding_authority_digest"],
        ["public.supplier_funding_authorities.funding_authority_id",
         "public.supplier_funding_authorities.authority_version",
         "public.supplier_funding_authorities.authority_digest"],
        name="fk_economic_receipts_funding_authority", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.ForeignKeyConstraint(
        ["supersedes_receipt_id", "usage_event_id", "execution_id", "task_id", "organization_id",
         "project_id", "actor_user_id", "dispatch_claim_id"],
        ["public.economic_receipts.economic_receipt_id", "public.economic_receipts.usage_event_id",
         "public.economic_receipts.execution_id", "public.economic_receipts.task_id",
         "public.economic_receipts.organization_id", "public.economic_receipts.project_id",
         "public.economic_receipts.actor_user_id", "public.economic_receipts.dispatch_claim_id"],
        name="fk_economic_receipts_supersession_binding", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.CheckConstraint("currency='USD'", name=conv("ck_economic_receipts_currency")),
    sa.CheckConstraint("assessment_status IN ('COMPUTED','INCOMPLETE_USAGE','UNAVAILABLE_USAGE','MISSING_PRICING')",
                       name=conv("ck_economic_receipts_status")),
    sa.CheckConstraint("cost_bearer IN ('JOUS_BORNE','CUSTOMER_DIRECT','UNKNOWN')",
                       name=conv("ck_economic_receipts_bearer")),
    sa.CheckConstraint("cost_bearer='UNKNOWN' OR funding_authority_id IS NOT NULL",
                       name=conv("ck_economic_receipts_bearer_authority")),
    sa.CheckConstraint("octet_length(assessment_key)=32 AND octet_length(treatment_policy_digest)=32 AND "
                       "octet_length(source_usage_digest)=32 AND octet_length(canonical_digest)=32 AND "
                       "(pricing_snapshot_sha256 IS NULL OR octet_length(pricing_snapshot_sha256)=32) AND "
                       "((funding_authority_id IS NULL AND funding_authority_version IS NULL AND funding_authority_digest IS NULL) OR "
                       "(funding_authority_id IS NOT NULL AND funding_authority_version IS NOT NULL AND "
                       "funding_authority_version>0 AND funding_authority_digest IS NOT NULL AND "
                       "octet_length(funding_authority_digest)=32))",
                       name=conv("ck_economic_receipts_digest_lengths")),
    sa.CheckConstraint("assessment_key=pg_catalog.sha256(pg_catalog.convert_to(pg_catalog.jsonb_build_object("
                       "'schema_version','jous.economic-assessment.v1','usage_event_id',usage_event_id,"
                       "'economic_policy_version',economic_policy_version,'treatment_policy_digest',"
                       "pg_catalog.encode(treatment_policy_digest,'hex'),'calculation_version',calculation_version,"
                       "'pricing_version_id',pricing_version_id,'funding_authority_digest',"
                       "CASE WHEN funding_authority_digest IS NULL THEN NULL ELSE "
                       "pg_catalog.encode(funding_authority_digest,'hex') END)::text,'UTF8'))",
                       name=conv("ck_economic_receipts_assessment_key")),
    sa.CheckConstraint("(pricing_snapshot_canonical IS NULL) = (pricing_snapshot_sha256 IS NULL) AND "
                       "(pricing_snapshot_canonical IS NULL OR "
                       "pricing_snapshot_sha256=pg_catalog.sha256(pg_catalog.convert_to(pricing_snapshot_canonical,'UTF8')))",
                       name=conv("ck_economic_receipts_pricing_snapshot_digest")),
    sa.CheckConstraint("(assessment_status='COMPUTED' AND route_decision_id IS NOT NULL AND pricing_version_id IS NOT NULL "
                       "AND provider_usage_cost_usd IS NOT NULL AND provider_request_fee_usd IS NOT NULL "
                       "AND gateway_request_fee_usd IS NOT NULL AND computed_usage_cost_usd IS NOT NULL "
                       "AND provider_usage_cost_usd>=0 AND provider_request_fee_usd>=0 AND gateway_request_fee_usd>=0 "
                       "AND computed_usage_cost_usd=provider_usage_cost_usd+provider_request_fee_usd+gateway_request_fee_usd "
                       "AND pricing_snapshot_canonical IS NOT NULL AND pricing_snapshot_sha256 IS NOT NULL) OR "
                       "(assessment_status<>'COMPUTED' AND provider_usage_cost_usd IS NULL AND provider_request_fee_usd IS NULL "
                       "AND gateway_request_fee_usd IS NULL AND computed_usage_cost_usd IS NULL)",
                       name=conv("ck_economic_receipts_amount_state")),
    sa.CheckConstraint("supersedes_receipt_id IS NULL OR supersedes_receipt_id<>economic_receipt_id",
                       name=conv("ck_economic_receipts_no_self_supersession")),
    sa.CheckConstraint("length(btrim(economic_policy_version))>0 AND length(btrim(calculation_version))>0 AND "
                       "pg_catalog.isfinite(observed_at) AND pg_catalog.isfinite(recorded_at)",
                       name=conv("ck_economic_receipts_identity")),
)
sa.Index("ix_economic_receipts_org_project_recorded", economic_receipts.c.organization_id,
         economic_receipts.c.project_id, economic_receipts.c.recorded_at,
         economic_receipts.c.economic_receipt_id)


ledger_accounts = sa.Table(
    "ledger_accounts", Base.metadata,
    sa.Column("ledger_account_id", UUID(as_uuid=True), nullable=False),
    sa.Column("account_code", sa.String(64), nullable=False),
    sa.Column("economic_classification", sa.String(64), nullable=False),
    sa.Column("normal_side", sa.String(6), nullable=False),
    sa.Column("currency", CHAR(3), nullable=False),
    sa.Column("postable", sa.Boolean(), nullable=False),
    sa.Column("account_version", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("ledger_account_id", name="pk_ledger_accounts"),
    sa.UniqueConstraint("account_code", name="uq_ledger_accounts_code"),
    sa.UniqueConstraint("ledger_account_id", "currency", name="uq_ledger_accounts_binding"),
    sa.CheckConstraint("currency='USD'", name=conv("ck_ledger_accounts_currency")),
    sa.CheckConstraint("normal_side IN ('DEBIT','CREDIT')", name=conv("ck_ledger_accounts_normal_side")),
    sa.CheckConstraint("account_version>0 AND length(btrim(account_code))>0 AND postable",
                       name=conv("ck_ledger_accounts_identity")),
    sa.CheckConstraint("(account_code='provider_inference_expense' AND economic_classification='PROVIDER_INFERENCE_EXPENSE' AND normal_side='DEBIT') OR "
                       "(account_code='gateway_platform_expense' AND economic_classification='GATEWAY_PLATFORM_EXPENSE' AND normal_side='DEBIT') OR "
                       "(account_code='supplier_cost_accrual' AND economic_classification='SUPPLIER_COST_ACCRUAL' AND normal_side='CREDIT')",
                       name=conv("ck_ledger_accounts_initial_taxonomy")),
)


ledger_transactions = sa.Table(
    "ledger_transactions", Base.metadata,
    sa.Column("ledger_transaction_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("economic_receipt_id", UUID(as_uuid=True), nullable=False),
    sa.Column("posting_purpose", sa.String(64), nullable=False),
    sa.Column("idempotency_key", BYTEA(), nullable=False),
    sa.Column("currency", CHAR(3), nullable=False),
    sa.Column("source_digest", BYTEA(), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True),
              server_default=sa.text("statement_timestamp()"), nullable=False),
    sa.PrimaryKeyConstraint("ledger_transaction_id", name="pk_ledger_transactions"),
    sa.UniqueConstraint("idempotency_key", name="uq_ledger_transactions_idempotency"),
    sa.UniqueConstraint("economic_receipt_id", "posting_purpose", name="uq_ledger_transactions_receipt_purpose"),
    sa.UniqueConstraint("ledger_transaction_id", "organization_id", "currency",
                        name="uq_ledger_transactions_entry_binding"),
    sa.ForeignKeyConstraint(["economic_receipt_id", "organization_id", "source_digest"],
        ["public.economic_receipts.economic_receipt_id", "public.economic_receipts.organization_id",
         "public.economic_receipts.canonical_digest"], name="fk_ledger_transactions_receipt_binding",
        ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.CheckConstraint("currency='USD'", name=conv("ck_ledger_transactions_currency")),
    sa.CheckConstraint("posting_purpose='COMPUTED_JOUS_COST_V1'",
                       name=conv("ck_ledger_transactions_posting_purpose")),
    sa.CheckConstraint("octet_length(idempotency_key)=32 AND octet_length(source_digest)=32",
                       name=conv("ck_ledger_transactions_digest_lengths")),
    sa.CheckConstraint("idempotency_key=pg_catalog.sha256(pg_catalog.convert_to(" 
                       "pg_catalog.jsonb_build_object('schema_version','jous.ledger-posting.v1',"
                       "'economic_receipt_id',economic_receipt_id,'posting_purpose',posting_purpose)::text,'UTF8'))",
                       name=conv("ck_ledger_transactions_idempotency_identity")),
    sa.CheckConstraint("pg_catalog.isfinite(recorded_at)", name=conv("ck_ledger_transactions_identity")),
)


ledger_entries = sa.Table(
    "ledger_entries", Base.metadata,
    sa.Column("ledger_transaction_id", UUID(as_uuid=True), nullable=False),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("line_number", sa.SmallInteger(), nullable=False),
    sa.Column("ledger_account_id", UUID(as_uuid=True), nullable=False),
    sa.Column("currency", CHAR(3), nullable=False),
    sa.Column("direction", sa.String(6), nullable=False),
    sa.Column("amount", sa.Numeric(50, 18), nullable=False),
    sa.PrimaryKeyConstraint("ledger_transaction_id", "line_number", name="pk_ledger_entries"),
    sa.UniqueConstraint("ledger_transaction_id", "ledger_account_id", "direction",
                        name="uq_ledger_entries_account_direction"),
    sa.ForeignKeyConstraint(["ledger_transaction_id", "organization_id", "currency"],
        ["public.ledger_transactions.ledger_transaction_id", "public.ledger_transactions.organization_id",
         "public.ledger_transactions.currency"], name="fk_ledger_entries_transaction_binding",
        ondelete="RESTRICT", onupdate="RESTRICT", deferrable=True, initially="DEFERRED"),
    sa.ForeignKeyConstraint(["ledger_account_id", "currency"],
        ["public.ledger_accounts.ledger_account_id", "public.ledger_accounts.currency"],
        name="fk_ledger_entries_account_currency", ondelete="RESTRICT", onupdate="RESTRICT"),
    sa.CheckConstraint("currency='USD'", name=conv("ck_ledger_entries_currency")),
    sa.CheckConstraint("line_number>0 AND amount>0", name=conv("ck_ledger_entries_positive")),
    sa.CheckConstraint("direction IN ('DEBIT','CREDIT')", name=conv("ck_ledger_entries_direction")),
)
sa.Index("ix_ledger_entries_org_transaction", ledger_entries.c.organization_id,
         ledger_entries.c.ledger_transaction_id, ledger_entries.c.line_number)
