"""Remove every non-owner relation ACL from the V1.2 product tables.

This migration is intentionally one-way. The pre-migration ACLs may include
managed or third-party grants whose original provenance cannot be reconstructed.
"""
from alembic import op

revision = '0004_product_acl_hardening'
down_revision = '0003_project_tasks_executions'
branch_labels = depends_on = None

UPGRADE_SQL = (
    'SET LOCAL search_path = pg_catalog',
    r"""DO $acl_hardening$
DECLARE
    target record;
    relation_count integer := 0;
    grantee_oid oid;
    grantee_name name;
    grantee_sql text;
    non_owner_acl_exists boolean;
BEGIN
    IF (SELECT pg_catalog.count(*)
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('tasks', 'executions')
          AND c.relkind = 'r') <> 2 THEN
        RAISE EXCEPTION 'Expected public.tasks and public.executions';
    END IF;

    FOR target IN
        SELECT c.relname, c.relowner, c.relacl
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('tasks', 'executions')
          AND c.relkind = 'r'
        ORDER BY c.relname
    LOOP
        relation_count := relation_count + 1;

        FOR grantee_oid IN
            SELECT DISTINCT acl.grantee
            FROM pg_catalog.aclexplode(
                COALESCE(target.relacl, pg_catalog.acldefault('r', target.relowner))
            ) AS acl
            WHERE acl.grantee <> target.relowner
            ORDER BY acl.grantee
        LOOP
            IF grantee_oid = 0 THEN
                grantee_sql := 'PUBLIC';
            ELSE
                SELECT r.rolname INTO grantee_name
                FROM pg_catalog.pg_roles r
                WHERE r.oid = grantee_oid;
                IF grantee_name IS NULL THEN
                    RAISE EXCEPTION 'Relation ACL grantee role is missing';
                END IF;
                grantee_sql := pg_catalog.quote_ident(grantee_name::text);
            END IF;

            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %s',
                target.relname, grantee_sql
            );
        END LOOP;
    END LOOP;

    IF relation_count <> 2 THEN
        RAISE EXCEPTION 'Product relation ACL cleanup did not inspect both tables';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace,
             LATERAL pg_catalog.aclexplode(
                 COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
             ) AS acl
        WHERE n.nspname = 'public'
          AND c.relname IN ('tasks', 'executions')
          AND c.relkind = 'r'
          AND acl.grantee <> c.relowner
    ) INTO non_owner_acl_exists;

    IF non_owner_acl_exists THEN
        RAISE EXCEPTION 'Non-owner product relation ACL remains';
    END IF;
END
$acl_hardening$""",
)


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    # A safe inverse cannot recreate unknown pre-0004 grants. Keep the
    # least-privilege ACL state rather than inventing third-party privileges.
    pass
