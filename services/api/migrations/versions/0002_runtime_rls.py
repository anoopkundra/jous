"""Reviewed security infrastructure only; role bootstrap is a separate operation."""
from alembic import op

revision = "0002_runtime_rls"
down_revision = "0001_identity_project"
branch_labels = depends_on = None
TABLES = ("users", "organizations", "organization_memberships", "projects")


def context_uuid(name):
    # Only constant, migration-owned names enter this SQL. CASE guards the cast.
    value = f"pg_catalog.current_setting('jous.{name}', true)"
    return (f"(CASE WHEN pg_catalog.length({value}) = 36 AND {value} OPERATOR(pg_catalog.~) "
            "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "
            f"THEN CAST({value} AS pg_catalog.uuid) ELSE NULL END)")


USER = context_uuid("user_id")
ORG = context_uuid("organization_id")
ACTIVE_USER = f"EXISTS (SELECT 1 FROM public.users u WHERE u.id = {USER} AND u.status = 'active')"
MEMBER = (f"user_id = {USER} AND status = 'active' AND role IN ('owner', 'member') AND {ACTIVE_USER} "
          "AND jous_security.organization_is_active(organization_id) AND "
          f"(COALESCE(pg_catalog.current_setting('jous.organization_id', true), '') = '' OR organization_id = {ORG})")
ORGANIZATION = (f"id = {ORG} AND status = 'active' AND EXISTS "
                "(SELECT 1 FROM public.organization_memberships m WHERE m.organization_id = organizations.id)")
PROJECT = (f"organization_id = {ORG} AND EXISTS "
           "(SELECT 1 FROM public.organizations o WHERE o.id = projects.organization_id)")
GUARDS = {"users": f"id = {USER} AND status = 'active'", "organization_memberships": MEMBER,
          "organizations": ORGANIZATION, "projects": PROJECT}
COMMANDS = {"users": ("SELECT",), "organization_memberships": ("SELECT",),
            "organizations": ("SELECT", "UPDATE"), "projects": ("SELECT", "INSERT", "UPDATE")}


def upgrade():
    op.execute("SET LOCAL search_path = pg_catalog")
    # Preconditions also appear in offline SQL. Never repurpose existing objects/ACLs.
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'
        AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
        AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit)
        OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='jous_security_reader'
        AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
        AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit)
        THEN RAISE EXCEPTION 'Jous role preconditions failed'; END IF;
      IF NOT pg_catalog.has_schema_privilege('jous_runtime','public','USAGE')
        OR NOT pg_catalog.has_schema_privilege('jous_security_reader','public','USAGE')
        THEN RAISE EXCEPTION 'public USAGE bootstrap prerequisite missing'; END IF;
      IF EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.member
                 WHERE r.rolname IN ('jous_runtime','jous_security_reader'))
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='jous_security')
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_policies WHERE schemaname='public'
                   AND tablename IN ('users','organizations','organization_memberships','projects'))
        THEN RAISE EXCEPTION 'Unexpected Jous security baseline'; END IF;
      IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relname IN ('users','organizations','organization_memberships','projects')
          AND c.relkind='r' AND c.relrowsecurity AND NOT c.relforcerowsecurity) <> 4
        THEN RAISE EXCEPTION 'Expected RLS-enabled baseline'; END IF;
    END $$""")
    # New roles must have no pre-existing Jous grants. This ensures a bounded downgrade.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM information_schema.role_table_grants WHERE grantee IN
        ('jous_runtime','jous_security_reader') AND table_schema='public') OR EXISTS
        (SELECT 1 FROM information_schema.role_column_grants WHERE grantee IN
        ('jous_runtime','jous_security_reader') AND table_schema='public')
        THEN RAISE EXCEPTION 'Unexpected pre-existing role grants'; END IF;
    END $$""")
    op.execute("CREATE SCHEMA jous_security")
    op.execute("REVOKE ALL ON SCHEMA jous_security FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA jous_security TO jous_runtime, jous_security_reader")
    op.execute("GRANT SELECT (id, auth_issuer, auth_subject, status) ON public.users TO jous_security_reader")
    op.execute("GRANT SELECT (id, status) ON public.organizations TO jous_security_reader")
    op.execute("""CREATE FUNCTION jous_security.resolve_user(p_issuer text, p_subject text)
      RETURNS uuid LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
      SET search_path = pg_catalog, pg_temp AS $function$
        SELECT u.id FROM public.users AS u
        WHERE p_issuer IS NOT NULL AND p_subject IS NOT NULL
          AND pg_catalog.length(p_issuer) BETWEEN 1 AND 255
          AND pg_catalog.length(p_subject) BETWEEN 1 AND 255
          AND pg_catalog.length(pg_catalog.btrim(p_issuer)) > 0
          AND pg_catalog.length(pg_catalog.btrim(p_subject)) > 0
          AND u.auth_issuer OPERATOR(pg_catalog.=) p_issuer
          AND u.auth_subject OPERATOR(pg_catalog.=) p_subject
          AND u.status OPERATOR(pg_catalog.=) 'active'::pg_catalog.varchar
      $function$""")
    op.execute("""CREATE FUNCTION jous_security.organization_is_active(p_organization_id uuid)
      RETURNS boolean LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
      SET search_path = pg_catalog, pg_temp AS $function$
        SELECT EXISTS (SELECT 1 FROM public.organizations o
          WHERE o.id OPERATOR(pg_catalog.=) p_organization_id
            AND o.status OPERATOR(pg_catalog.=) 'active'::pg_catalog.varchar)
      $function$""")
    # ALTER FUNCTION OWNER requires CREATE for the new owner. Revoke before commit.
    op.execute("GRANT CREATE ON SCHEMA jous_security TO jous_security_reader")
    for signature in ("resolve_user(text, text)", "organization_is_active(uuid)"):
        op.execute(f"REVOKE ALL ON FUNCTION jous_security.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION jous_security.{signature} TO jous_runtime")
        # Finish ACLs as creator; SET capability alone does not inherit owner rights.
        op.execute(f"ALTER FUNCTION jous_security.{signature} OWNER TO jous_security_reader")
    op.execute("REVOKE CREATE ON SCHEMA jous_security FROM jous_security_reader")
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        guard = GUARDS[table]
        op.execute(f"CREATE POLICY jous_{table}_guard ON public.{table} AS RESTRICTIVE "
                   f"FOR ALL TO jous_runtime USING ({guard}) WITH CHECK ({guard})")
        for command in COMMANDS[table]:
            clause = f"WITH CHECK ({guard})" if command == "INSERT" else f"USING ({guard})"
            if command == "UPDATE":
                clause += f" WITH CHECK ({guard})"
            op.execute(f"CREATE POLICY jous_{table}_{command.lower()} ON public.{table} "
                       f"FOR {command} TO jous_runtime {clause}")
    for table in ("users", "organizations"):
        op.execute(f"CREATE POLICY jous_{table}_helper_read ON public.{table} FOR SELECT "
                   "TO jous_security_reader USING (true)")
    op.execute("GRANT SELECT (id, status) ON public.users TO jous_runtime")
    for table in ("organizations", "organization_memberships", "projects"):
        # Explicit columns: future columns never receive automatic visibility.
        columns = {"organizations": "id, name, status, created_at, updated_at",
                   "organization_memberships": "id, user_id, organization_id, role, status, created_at, updated_at",
                   "projects": "id, organization_id, name, description, status, created_at, updated_at"}[table]
        op.execute(f"GRANT SELECT ({columns}) ON public.{table} TO jous_runtime")
    op.execute("GRANT SELECT ON public.alembic_version TO jous_runtime")
    op.execute("GRANT UPDATE (name, updated_at) ON public.organizations TO jous_runtime")
    op.execute("GRANT INSERT (id, organization_id, name, description) ON public.projects TO jous_runtime")
    op.execute("GRANT UPDATE (name, description, updated_at) ON public.projects TO jous_runtime")


def downgrade():
    op.execute("SET LOCAL search_path = pg_catalog")
    # Preserve pre-existing ENABLE RLS. No table, role or managed object deletion.
    for table in TABLES:
        for command in COMMANDS[table]:
            op.execute(f"DROP POLICY jous_{table}_{command.lower()} ON public.{table}")
        op.execute(f"DROP POLICY jous_{table}_guard ON public.{table}")
        if table in ("users", "organizations"):
            op.execute(f"DROP POLICY jous_{table}_helper_read ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
        for role in ("jous_runtime", "jous_security_reader"):
            op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM {role}")
            # Table-level REVOKE does not remove column ACLs.
            columns = {"users": "id, auth_issuer, auth_subject, status, created_at, updated_at",
                "organizations": "id, name, status, created_at, updated_at",
                "organization_memberships": "id, user_id, organization_id, role, status, created_at, updated_at",
                "projects": "id, organization_id, name, description, status, created_at, updated_at"}[table]
            for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                op.execute(f"REVOKE {privilege} ({columns}) ON public.{table} FROM {role}")
    op.execute("REVOKE SELECT ON public.alembic_version FROM jous_runtime")
    op.execute("DROP FUNCTION jous_security.resolve_user(text, text)")
    op.execute("DROP FUNCTION jous_security.organization_is_active(uuid)")
    op.execute("DROP SCHEMA jous_security")
    # public USAGE is a bootstrap prerequisite; do not remove pre-existing grants.
