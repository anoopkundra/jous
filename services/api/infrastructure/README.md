# Step 7 controlled infrastructure

These artifacts have not been executed. No local PostgreSQL installation is needed.
Use the dedicated managed project and Session Pooler with verified TLS.

## Mandatory managed-change stop

Before any mutation, capture the target fingerprint, PostgreSQL version, migration
revision (0001), actual ownership, existing RLS/policies and effective PUBLIC/role
grants. Have the founder review that evidence and approve execution. Stop if shared
Supabase privileges must change; do not alter managed roles, objects or schemas.

Runtime guards reject effective database CREATE, permanent schema CREATE,
object/database ownership, memberships and unrelated table access. The approved
compatibility exception accepts either no TEMP privilege or TEMP supplied solely
by PUBLIC without grant option. Explicit runtime TEMP grants remain prohibited.
Supabase currently exposes PUBLIC TEMP; do not change shared managed-role ACLs.
The validator reports MANAGED_PUBLIC_TEMP_BASELINE from checked catalog evidence.
Jous's normal runtime does not require or create temporary objects. TEMP retains
resource-exhaustion and name-shadowing risk; objects can survive commit and pooled
session reuse. Privileged helpers must keep hardened search_path and qualified
protected relations to resist pg_temp shadowing. This residual capability does
not change tenant/RLS architecture or application action authorization.

`runtime_roles.sql` refuses any conflicting existing role. It creates no password,
role memberships, or jous_owner. Existing administrative ownership remains. The
administrator must be able to create the private schema, assign helper ownership,
and manage policies on the four Jous tables. Never solve insufficient authority by
giving runtime privileged membership. Record any separately approved admin grants.

## Ordering

1. Complete offline tests and security review.
2. Read-only managed preflight and founder stop/review before mutations.
3. Execute the reviewed role bootstrap; inspect restricted attributes/memberships.
4. With only `JOUS_MIGRATION_DATABASE_URL` in migration tooling, upgrade to
   `0002_runtime_rls`; inspect functions, ACLs, policies and ENABLE/FORCE flags.
5. Activate a runtime password securely outside source, SQL artifacts and logs.
   Export `JOUS_DATABASE_URL` for the actual `jous_runtime` login. Do not reuse admin.
6. Run the explicitly opted-in managed validator with both separately held URLs.
7. Verify fixture cleanup, unchanged managed objects, counts and final revision.
8. Security review and separate PUBLIC CRUD SECURITY GATE. No CRUD is implemented.

The schema owner temporarily grants CREATE on the new private schema to the helper
owner solely to assign function ownership, then revokes it before migration commit.
For a non-superuser PostgreSQL 17 migration admin, ownership transfer also requires
SET capability to jous_security_reader; ADMIN OPTION alone is insufficient. Obtain
that capability only through a separately authorized temporary prerequisite, keeping
INHERIT false. It is not permanent runtime or role-bootstrap authority. Complete
PUBLIC revocation and runtime EXECUTE grants while the admin still owns each helper;
ownership transfer is the final function-management operation for that helper during
upgrade. Verify migration ownership/ACLs, then remove temporary SET authority with
grantor-aware membership cleanup and verify the final membership state. Prefer one
controlled transaction encompassing prerequisite, migration, verification and cleanup;
if separately committed, a migration failure requires explicit prerequisite cleanup.
Future helper changes require bounded owner maintenance: temporary SET capability,
an explicit helper-owner role section where owner commands are needed, restoration
of the admin role, and removal of temporary authority before commit. The admin-owned
helper schema permits the existing PostgreSQL 17 downgrade to drop its contained
helpers without permanent SET capability; verify schema ownership before downgrade.
Helper SELECT policies are role-specific and read-only. Ordinary GUCs are not a
cryptographic boundary against someone executing arbitrary SQL with runtime login.

## Validation and recovery

Use `tests/validate_managed_runtime_security.py --help` offline for options. Require
a caller-provided target fingerprint and cleanup manifest path. The fingerprint
uses host/port/database/public project reference, excluding credentials; both logins must also identify the
same server-side database. The manifest contains generated UUIDs and target metadata,
never secrets. Fixtures are administratively committed so real runtime connections
can see them. Runtime mutations roll back. Cleanup deletes only recorded rows in
Project, Membership, Organization, User order. Keep manifests until baseline checks
pass; `--cleanup-only` retries exact cleanup after an interrupted process.

Partial bootstrap requires inventory/review, not automatic role replacement.
Migration errors require revision/transaction-state inspection before retry.
Connection, ACL, ownership or recursive-policy failures keep runtime traffic blocked.
Do not disable RLS or add broad policies to make a failing test pass.

An explicitly authorized downgrade targets `0001_identity_project`, never base. It
removes Step 7 objects/grants and FORCE while retaining the required pre-existing
ENABLE RLS state. Role lifecycle and credential deactivation are separate tasks.
Unresolved fixture cleanup is a failure and needs targeted administrative recovery.

Runtime ORM metadata explicitly targets public for all four domain relations;
authorization queries cannot resolve same-named pg_temp relations. Offline compiled
SQL checks are not live isolation evidence. A later separately authorized managed
validator must exercise actual temporary-shadow scenarios before the security gate.
