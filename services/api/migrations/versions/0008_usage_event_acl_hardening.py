"""Remove inherited public-table ACLs and harden future public defaults."""
from alembic import op


revision = "0008_usage_event_acl_hardening"
down_revision = "0007_usage_events"
branch_labels = None
depends_on = None


UPGRADE_SQL = (
    r"""DO $preflight$
BEGIN
  IF current_user <> 'postgres' THEN
    RAISE EXCEPTION 'Migration owner must be postgres';
  END IF;
  IF (SELECT count(*) FROM public.alembic_version) <> 1 OR
     (SELECT max(version_num) FROM public.alembic_version) <> '0007_usage_events' THEN
    RAISE EXCEPTION 'Expected migration revision 0007_usage_events';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class
      WHERE oid='public.usage_events'::pg_catalog.regclass
        AND pg_catalog.pg_get_userbyid(relowner)='postgres') THEN
    RAISE EXCEPTION 'Unexpected usage_events owner';
  END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('anon','authenticated','service_role')) <> 3 THEN
    RAISE EXCEPTION 'Required Supabase roles are missing';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_default_acl d
    CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
    WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
      AND d.defaclobjtype='r' AND d.defaclnamespace=0
      AND a.grantee IN (0,
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'))
      AND a.privilege_type IN ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE',
                               'REFERENCES','TRIGGER','MAINTAIN')
  ) THEN
    RAISE EXCEPTION 'Unsafe global postgres table defaults require separate review';
  END IF;
END
$preflight$""",
    "REVOKE TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLE public.usage_events FROM anon, authenticated, service_role",
    "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLES FROM anon, authenticated, service_role",
    r"""DO $postcondition$
BEGIN
  IF EXISTS (
    SELECT 1 FROM (VALUES ('anon'),('authenticated'),('service_role'),
                          ('jous_runtime'),('jous_security_reader')) r(name)
    CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),
                       ('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(privilege)
    WHERE pg_catalog.has_table_privilege(r.name,'public.usage_events',p.privilege)
  ) THEN
    RAISE EXCEPTION 'Unexpected effective usage_events table authority remains';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_default_acl d
    CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) a
    WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres')
      AND d.defaclobjtype='r' AND d.defaclnamespace IN
        (0,(SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='public'))
      AND a.grantee IN (0,
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='anon'),
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='authenticated'),
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='service_role'))
  ) THEN
    RAISE EXCEPTION 'Unexpected postgres/public table default authority remains';
  END IF;
END
$postcondition$""",
)


def upgrade():
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade():
    # Security hardening is monotonic; never restore unsafe ACLs on downgrade.
    pass
