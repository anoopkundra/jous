"""Initial identity and Project ownership foundation. No external schemas are modified."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_identity_project"
down_revision = None
branch_labels = None
depends_on = None


def record_columns():
    # Frozen revision definitions, intentionally independent of current ORM models.
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade():
    op.create_table(
        "users", *record_columns(),
        sa.Column("auth_issuer", sa.String(255), nullable=True),
        sa.Column("auth_subject", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("auth_issuer", "auth_subject", name="uq_users_auth_identity"),
        sa.CheckConstraint("(auth_issuer IS NULL AND auth_subject IS NULL) OR "
                           "(auth_issuer IS NOT NULL AND auth_subject IS NOT NULL AND "
                           "length(btrim(auth_issuer)) > 0 AND length(btrim(auth_subject)) > 0)",
                           name=op.f("ck_users_auth_identity_pair")),
        sa.CheckConstraint("length(btrim(status)) > 0", name=op.f("ck_users_status_nonblank")),
        schema="public")
    op.create_table(
        "organizations", *record_columns(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_organizations_name_nonblank")),
        sa.CheckConstraint("length(btrim(status)) > 0", name=op.f("ck_organizations_status_nonblank")),
        schema="public")
    op.create_table(
        "organization_memberships", *record_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), server_default="member", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.ForeignKeyConstraint(["organization_id"], ["public.organizations.id"],
                                name="fk_organization_memberships_organization_id_organizations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"],
                                name="fk_organization_memberships_user_id_users", ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_organization_user"),
        sa.CheckConstraint("length(btrim(role)) > 0", name=op.f("ck_organization_memberships_role_nonblank")),
        sa.CheckConstraint("length(btrim(status)) > 0", name=op.f("ck_organization_memberships_status_nonblank")),
        schema="public")
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"], schema="public")
    op.create_table(
        "projects", *record_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.ForeignKeyConstraint(["organization_id"], ["public.organizations.id"],
                                name="fk_projects_organization_id_organizations", ondelete="RESTRICT"),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_projects_name_nonblank")),
        sa.CheckConstraint("length(btrim(status)) > 0", name=op.f("ck_projects_status_nonblank")),
        schema="public")
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], schema="public")


def downgrade():
    # No CASCADE: unexpected dependent objects must stop the downgrade.
    op.drop_index("ix_projects_organization_id", table_name="projects", schema="public")
    op.drop_table("projects", schema="public")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships", schema="public")
    op.drop_table("organization_memberships", schema="public")
    op.drop_table("organizations", schema="public")
    op.drop_table("users", schema="public")
